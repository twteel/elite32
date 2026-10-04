"""Put the show's intro on the front and the outro on the back of every episode that's missing them.

The intro plays first and FADES OUT into the episode; at the end the episode FADES INTO the outro
(video crossfade + audio crossfade). By default the outro is the intro played in reverse, so the
episode dissolves into the empty court and the lockup fades IN and holds as the last frame.

Episodes that already have it are left alone: the script compares frames from the intro clip with
the first / last minute of each episode and only adds what's missing.

Usage:
  python intro_outro.py --intro brand/b4p/intro.mp4 episodes/*.mp4
  python intro_outro.py --intro intro.mp4 --outro outro.mp4 --fade 1.5 "~/Videos/B4P Ep 13.mp4"
  python intro_outro.py --intro intro.mp4 --check episodes/*.mp4     # just report, change nothing

Output: <name> (intro+outro).mp4 next to the original (or --out <folder>). Originals are never touched.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    num, den = (v.get("avg_frame_rate") or v["r_frame_rate"]).split("/")
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": float(num) / float(den or 1),
            "dur": float(d["format"]["duration"]), "audio": a is not None,
            "rate": int(a["sample_rate"]) if a else 48000}


def thumbs(path, start, length, step=0.5):
    """Tiny grayscale frames (32x18) every `step` seconds - enough to recognise the intro."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, start)), "-t", str(length), "-i", str(path),
                          "-vf", f"fps={1 / step},scale=32:18,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 18 * 32).astype(float)


def best_match(needle, hay):
    """Smallest mean per-pixel difference between the intro's frames and any window of the episode."""
    n = len(needle)
    if len(hay) < n or n == 0:
        return 255.0
    return min(np.abs(hay[i:i + n] - needle).mean() for i in range(len(hay) - n + 1))


def has_clip(episode, clip, ep_info, clip_info, where):
    """True if `clip` (its middle 4 seconds) already appears in the first/last 90s of the episode."""
    mid = max(0, clip_info["dur"] / 2 - 2)
    needle = thumbs(clip, mid, 4)
    span = min(90, ep_info["dur"])
    start = 0 if where == "start" else ep_info["dur"] - span
    return best_match(needle, thumbs(episode, start, span)) < 18  # 0 = identical, ~60+ = unrelated


def build(episode, intro, outro, info, add_intro, add_outro, fade, out):
    W, H, fps, rate = info["w"], info["h"], round(info["fps"], 3), info["rate"]
    norm_v = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"
    norm_a = f"aresample={rate},aformat=sample_fmts=fltp:channel_layouts=stereo"
    inputs, parts = [], []
    if add_intro:
        inputs += ["-i", str(intro)]
        parts.append(("intro", probe(intro)))
    inputs += ["-i", str(episode)]
    parts.append(("ep", info))
    if add_outro:
        inputs += ["-i", str(outro)]
        parts.append(("outro", probe(outro)))
    f = []
    for i, (name, p) in enumerate(parts):
        f.append(f"[{i}:v]{norm_v}[v{i}]")
        # clips with no sound get silence so the audio crossfade still lines up
        f.append(f"[{i}:a]{norm_a}[a{i}]" if p["audio"] else
                 f"anullsrc=r={rate}:cl=stereo,atrim=duration={p['dur']}[a{i}]")
    v, a, t = "v0", "a0", parts[0][1]["dur"]
    for i in range(1, len(parts)):
        f.append(f"[{v}][v{i}]xfade=transition=fade:duration={fade}:offset={t - fade:.3f}[vx{i}]")
        f.append(f"[{a}][a{i}]acrossfade=d={fade}:c1=tri:c2=tri[ax{i}]")
        v, a, t = f"vx{i}", f"ax{i}", t + parts[i][1]["dur"] - fade
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", *inputs, "-filter_complex", ";".join(f), "-map", f"[{v}]", "-map", f"[{a}]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)


def reversed_copy(clip, size, cache_dir):
    """The intro played backwards (picture only; the sound plays forward), scaled to the episode size."""
    W, H = size
    out = Path(cache_dir) / f"{clip.stem}.reversed.{W}x{H}.mp4"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,reverse",
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episodes", nargs="+")
    ap.add_argument("--intro", required=True)
    ap.add_argument("--outro", help="a separate outro clip (default: the intro played in reverse)")
    ap.add_argument("--fade", type=float, default=1.0, help="crossfade seconds (default 1.0)")
    ap.add_argument("--out", help="output folder (default: next to each episode)")
    ap.add_argument("--check", action="store_true", help="only report which episodes need it")
    ap.add_argument("--force", action="store_true", help="add both even if they seem to be there")
    a = ap.parse_args()
    intro = Path(a.intro).expanduser()
    ii = probe(intro)
    for e in a.episodes:
        ep = Path(e).expanduser()
        info = probe(ep)
        outro = Path(a.outro).expanduser() if a.outro else reversed_copy(intro, (info["w"], info["h"]), Path(__file__).parent / "work" / "intro")
        oi = probe(outro)
        need_in = a.force or not has_clip(ep, intro, info, ii, "start")
        need_out = a.force or not has_clip(ep, outro, info, oi, "end")
        status = ", ".join(x for x, n in (("intro", need_in), ("outro", need_out)) if n) or "nothing (already has both)"
        print(f"{ep.name}: needs {status}")
        if a.check or not (need_in or need_out):
            continue
        dest = Path(a.out).expanduser() if a.out else ep.parent
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{ep.stem} (intro+outro).mp4"
        build(ep, intro, outro, info, need_in, need_out, a.fade, out)
        print(f"  -> {out}")


if __name__ == "__main__":
    sys.exit(main())
