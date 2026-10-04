"""Podcast cover-art pipeline.

frames  -> pull stills from each episode's video sources (ffmpeg)
faces   -> detect + embed every face (OpenCV YuNet / SFace)
pick    -> cluster faces across ALL episodes; recurring faces are the hosts,
           the biggest non-host cluster in an episode is the guest
cutout  -> crop around the guest, remove background (rembg), print treatment
render  -> fill the HTML template and screenshot every format (Playwright)

Usage:
  python pipeline.py import-opus clips1.json clips2.json ...
  python pipeline.py all            # every episode
  python pipeline.py all b4p-14     # one episode
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
OUT = ROOT / "out"
MODELS = ROOT / "models"
MODEL_URLS = {
    "face_detection_yunet_2023mar.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
FORMATS = {"yt": (1280, 720), "square": (1080, 1080), "vertical": (1080, 1920)}
SAME_PERSON = 0.40      # SFace cosine similarity; OpenCV's own threshold is 0.363
HOST_SHARE = 0.35       # a face seen in this share of episodes is a host


def load_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def save_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, indent=1))


def episodes(only=None):
    eps = load_json(os.environ.get("EPISODES", ROOT / "episodes.json"))
    return [e for e in eps if not only or e["id"] in only]


def model(name):
    path = MODELS / name
    if not path.exists():
        MODELS.mkdir(exist_ok=True)
        urllib.request.urlretrieve(MODEL_URLS[name], path)
    return str(path)


# ---------------------------------------------------------------- sources
def cmd_import_opus(files):
    """Map OpusClip list_clips dumps onto episodes as frame sources (top clips by score)."""
    by_project = {}
    for f in files:
        data = json.loads(Path(f).read_text())
        for c in data["clips"]:
            if not c.get("is_bonus"):
                by_project.setdefault(c["project_id"], []).append(c)
    for e in episodes():
        clips = sorted(by_project.get(e.get("opus_project"), []), key=lambda c: -c["score"])[:10]
        if clips:
            save_json(WORK / e["id"] / "sources.json",
                      [{"url": c["preview_url"], "thumb": c["thumbnail_url"], "title": c["title"]} for c in clips])
            print(f"{e['id']}: {len(clips)} clip sources")


# ---------------------------------------------------------------- frames
def cmd_frames(ep):
    d = WORK / ep["id"] / "frames"
    d.mkdir(parents=True, exist_ok=True)
    sources = ep.get("sources") or load_json(WORK / ep["id"] / "sources.json", [])
    for i, s in enumerate(sources):
        src = s if isinstance(s, str) else s["url"]
        if Path(src).suffix.lower() in (".jpg", ".jpeg", ".png"):
            Image.open(src).convert("RGB").save(d / f"s{i:02d}_0001.jpg", quality=95)
            continue
        long_video = Path(src).exists() and os.path.getsize(src) > 300_000_000
        rate = "1/8" if long_video else "1/2"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-vf", f"fps={rate}",
                        "-q:v", "2", str(d / f"s{i:02d}_%04d.jpg")], check=True)
    print(f"{ep['id']}: {len(list(d.glob('*.jpg')))} frames")


# ---------------------------------------------------------------- faces
def face_quality(img, f):
    x, y, w, h = f[:4]
    H, W = img.shape[:2]
    (rex, rey), (lex, ley), (nx, ny) = f[4:6], f[6:8], f[8:10]
    eye_dist = max(1.0, np.hypot(lex - rex, ley - rey))
    frontal = 1 - min(1, abs(nx - (rex + lex) / 2) / (eye_dist * 0.5))   # nose centred between eyes
    level = 1 - min(1, abs(ley - rey) / (eye_dist * 0.3))                # head not tilted
    crop = cv2.cvtColor(img[max(0, int(y)):int(y + h), max(0, int(x)):int(x + w)], cv2.COLOR_BGR2GRAY)
    sharp = min(1, np.log1p(cv2.Laplacian(crop, cv2.CV_64F).var()) / 7) if crop.size else 0
    size = min(1, (h / H) / 0.3)
    room = 1 if y + h * 2.2 < H else 0.6                                 # space for shoulders
    return float(f[14]) * (0.30 * frontal + 0.15 * level + 0.30 * sharp + 0.25 * size) * room


def cmd_faces(ep):
    det = cv2.FaceDetectorYN.create(model("face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.85)
    rec = cv2.FaceRecognizerSF.create(model("face_recognition_sface_2021dec.onnx"), "")
    found = []
    for fp in sorted((WORK / ep["id"] / "frames").glob("*.jpg")):
        img = cv2.imread(str(fp))
        H, W = img.shape[:2]
        det.setInputSize((W, H))
        _, faces = det.detect(img)
        for f in faces if faces is not None else []:
            if f[3] < H * 0.08:
                continue
            emb = rec.feature(rec.alignCrop(img, f)).flatten()
            found.append({"frame": str(fp.relative_to(ROOT)), "box": [float(v) for v in f[:4]],
                          "quality": face_quality(img, f),
                          "emb": (emb / np.linalg.norm(emb)).round(5).tolist()})
    save_json(WORK / ep["id"] / "faces.json", found)
    print(f"{ep['id']}: {len(found)} faces")


# ---------------------------------------------------------------- pick
def cluster(faces):
    cents, members = [], []
    for i, f in enumerate(faces):
        e = np.array(f["emb"])
        sims = [float(c @ e) / np.linalg.norm(c) for c in cents]
        k = int(np.argmax(sims)) if sims else -1
        if k >= 0 and sims[k] >= SAME_PERSON:
            cents[k] = cents[k] + e
            members[k].append(i)
        else:
            cents.append(e.copy())
            members.append([i])
    return members


def cmd_pick(eps):
    faces = []
    for ep in episodes():
        for f in load_json(WORK / ep["id"] / "faces.json", []):
            faces.append({**f, "ep": ep["id"]})
    if not faces:
        sys.exit("no faces found - run frames/faces first")
    groups = cluster(faces)
    n_eps = len({f["ep"] for f in faces})
    host_groups = set()
    for gi, g in enumerate(groups):
        seen = {faces[i]["ep"] for i in g}
        if n_eps >= 3 and len(seen) >= max(2, HOST_SHARE * n_eps):
            host_groups.add(gi)
    for ep in eps:
        if ep.get("guest_frame"):
            save_json(WORK / ep["id"] / "pick.json", {"frame": ep["guest_frame"], "box": ep.get("guest_box"), "why": "manual"})
            continue
        cands = []
        for gi, g in enumerate(groups):
            mine = [faces[i] for i in g if faces[i]["ep"] == ep["id"]]
            if mine and gi not in host_groups:
                cands.append((len(mine), gi, max(mine, key=lambda f: f["quality"])))
        cands.sort(key=lambda c: -c[0])
        if cands and cands[0][0] >= 2:
            n, gi, best = cands[0]
            pick = {"frame": best["frame"], "box": best["box"], "why": f"guest cluster {gi}: {n} frames"}
        else:
            pick = {"frame": None, "box": None, "why": "no guest face found - using no-guest layout"}
        save_json(WORK / ep["id"] / "pick.json", pick)
        print(f"{ep['id']}: {pick['why']}")


# ---------------------------------------------------------------- cutout + print treatment
_session = None


def remove_bg(img):
    global _session
    from rembg import new_session, remove
    _session = _session or new_session("u2net_human_seg")
    return remove(img, session=_session, post_process_mask=True)


def keep_subject(rgba, cx, cy):
    """Drop other people in the shot: keep the alpha blob that contains the face centre."""
    a = np.array(rgba.split()[-1])
    n, labels = cv2.connectedComponents((a > 40).astype(np.uint8))
    lab = labels[min(int(cy), a.shape[0] - 1), min(int(cx), a.shape[1] - 1)]
    if n > 1 and lab:
        a = np.where(labels == lab, a, 0).astype(np.uint8)
    rgba.putalpha(Image.fromarray(a))
    return rgba


def duotone(gray, ink, paper):
    ink, paper = np.array(ink, float), np.array(paper, float)
    t = (np.asarray(gray, float) / 255)[..., None]
    return Image.fromarray((ink + (paper - ink) * t).astype(np.uint8))


def halftone(gray, cell=7, angle=45):
    """Classic print dot screen of a grayscale image (dots = ink)."""
    g = gray.rotate(angle, expand=True, fillcolor=255)
    W, H = g.size
    small = np.asarray(g.resize((W // cell + 1, H // cell + 1), Image.BILINEAR), float) / 255
    dots = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(dots)
    for j in range(small.shape[0]):
        for i in range(small.shape[1]):
            r = cell * 0.72 * np.sqrt(1 - small[j, i])
            if r > 0.4:
                cx, cy = i * cell + cell / 2, j * cell + cell / 2
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    dots = dots.rotate(-angle, expand=True, fillcolor=255)
    l, t = (dots.width - gray.width) // 2, (dots.height - gray.height) // 2
    return dots.crop((l, t, l + gray.width, t + gray.height))


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def treat(cut, colors):
    """Cut-out -> duotone + halftone + white sticker border + hard drop shadow."""
    alpha = cut.split()[-1]
    gray = ImageOps.autocontrast(ImageOps.grayscale(cut.convert("RGB")), cutoff=2)
    gray = ImageOps.autocontrast(gray.point(lambda v: 255 * (v / 255) ** 0.9), cutoff=1)
    tone = duotone(gray, hex_rgb(colors["ink"]), hex_rgb(colors["paper"]))
    dots = halftone(gray, cell=max(5, cut.width // 140))
    ink = Image.new("RGB", cut.size, hex_rgb(colors["ink"]))
    tone = Image.composite(tone, Image.blend(tone, ink, 0.55), dots.point(lambda v: 255 if v > 128 else 0))
    pad = max(10, cut.width // 45)
    big = Image.new("RGBA", (cut.width + pad * 4, cut.height + pad * 2), (0, 0, 0, 0))
    a = Image.new("L", big.size, 0)
    a.paste(alpha, (pad * 2, pad))
    border = a.filter(ImageFilter.MaxFilter(pad * 2 + 1)).point(lambda v: 255 if v > 60 else 0)
    shadow = Image.new("RGBA", big.size, hex_rgb(colors.get("accent", colors["ink"])) + (255,))
    big.paste(shadow, (pad // 2 + 4, pad // 2 + 4), border)
    big.paste(Image.new("RGBA", big.size, (255, 255, 255, 255)), (0, 0), border)
    body = Image.new("RGBA", big.size, (0, 0, 0, 0))
    body.paste(tone.convert("RGBA"), (pad * 2, pad), alpha)
    return Image.alpha_composite(big, body).crop((0, 0, big.width, big.height - pad))


def cmd_cutout(ep, shows):
    pick = load_json(WORK / ep["id"] / "pick.json", {})
    if not pick.get("frame"):
        return
    img = Image.open(ROOT / pick["frame"]).convert("RGB")
    x, y, w, h = pick["box"] or [img.width * 0.35, img.height * 0.15, img.width * 0.3, img.height * 0.3]
    # head + shoulders: generous sides, room above the hair, down to the chest
    l, t = max(0, x - w * 1.35), max(0, y - h * 0.75)
    r, b = min(img.width, x + w * 2.35), min(img.height, y + h * 3.1)
    crop = img.crop((int(l), int(t), int(r), int(b)))
    if crop.height < 900:  # upscale small frames before effects so dots stay crisp
        s = 900 / crop.height
        crop = crop.resize((int(crop.width * s), 900), Image.LANCZOS)
    else:
        s = 1.0
    cut = keep_subject(remove_bg(crop), (x + w / 2 - l) * s, (y + h / 2 - t) * s)
    cut = cut.crop(cut.getbbox())
    cut.save(WORK / ep["id"] / "guest_cut.png")
    treat(cut, shows[ep["show"]]["colors"]).save(WORK / ep["id"] / "guest.png")
    print(f"{ep['id']}: cut-out done")


# ---------------------------------------------------------------- render
def cmd_render(eps, shows, formats):
    from playwright.sync_api import sync_playwright
    tpl = (ROOT / "template" / "cover.html").read_text()
    exe = os.environ.get("CHROMIUM_PATH") or next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")), None)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        for ep in eps:
            show = shows[ep["show"]]
            guest = WORK / ep["id"] / "guest.png"
            mark = ROOT / show["mark"] if show.get("mark") else None
            mark_path = re.search(r' d="([^"]+)"', mark.read_text()).group(1) if mark and mark.exists() else ""
            data = {"show": show, "markPath": mark_path, "ep": ep.get("ep"), "guest": ep.get("guest"), "hook": ep["hook"],
                    "img": guest.resolve().as_uri() if guest.exists() and load_json(WORK / ep["id"] / "pick.json", {}).get("frame") else None}
            html = WORK / ep["id"] / "cover.html"
            html.parent.mkdir(parents=True, exist_ok=True)
            html.write_text(tpl.replace("__DATA__", json.dumps(data)).replace("__TPL__", (ROOT / "template").as_uri()))
            for fmt in formats:
                W, H = FORMATS[fmt]
                page = browser.new_page(viewport={"width": W, "height": H})
                page.goto(f"{html.resolve().as_uri()}#{fmt}")
                page.wait_for_function("window.READY === true", timeout=30000)
                OUT.mkdir(exist_ok=True)
                page.screenshot(path=str(OUT / f"{ep['id']}_{fmt}.jpg"), type="jpeg", quality=92)
                page.close()
            print(f"{ep['id']}: rendered {', '.join(formats)}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["import-opus", "frames", "faces", "pick", "cutout", "render", "all"])
    ap.add_argument("ids", nargs="*", help="episode ids (default: all) or files for import-opus")
    ap.add_argument("--formats", default="yt,square,vertical")
    a = ap.parse_args()
    if a.step == "import-opus":
        return cmd_import_opus(a.ids)
    shows = load_json(ROOT / "shows.json")
    eps = episodes(a.ids)
    if a.step in ("frames", "all"):
        for ep in eps:
            cmd_frames(ep)
    if a.step in ("faces", "all"):
        for ep in eps:
            cmd_faces(ep)
    if a.step in ("pick", "all"):
        cmd_pick(eps)
    if a.step in ("cutout", "all"):
        for ep in eps:
            cmd_cutout(ep, shows)
    if a.step in ("render", "all"):
        cmd_render(eps, shows, a.formats.split(","))


if __name__ == "__main__":
    main()
