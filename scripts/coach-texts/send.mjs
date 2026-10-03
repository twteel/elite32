#!/usr/bin/env node
// Text individual Instagram post images (hosted in Google Drive) to coaches via Twilio MMS.
//
// Usage:
//   node scripts/coach-texts/send.mjs coaches.csv posts.csv          # dry run (prints, sends nothing)
//   node scripts/coach-texts/send.mjs coaches.csv posts.csv --send   # actually send
//
// coaches.csv columns: team,name,phone,consent       (consent must be "yes")
// posts.csv columns:   team,drive_file_id,caption
//
// Every post whose team matches a coach's team is texted to that coach.
// Env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER (E.164, e.g. +12125551234)

import { readFileSync } from 'node:fs';

const [coachesPath, postsPath, ...flags] = process.argv.slice(2);
const send = flags.includes('--send');
if (!coachesPath || !postsPath) {
  console.error('Usage: send.mjs coaches.csv posts.csv [--send]');
  process.exit(1);
}

function parseCsv(path) {
  const rows = [];
  let row = [], field = '', quoted = false;
  const text = readFileSync(path, 'utf8').replace(/^﻿/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.some((v) => v.trim())) rows.push(row);
      row = [];
    } else field += c;
  }
  row.push(field);
  if (row.some((v) => v.trim())) rows.push(row);
  const [header, ...body] = rows;
  const keys = header.map((h) => h.trim().toLowerCase());
  return body.map((r) => Object.fromEntries(keys.map((k, i) => [k, (r[i] ?? '').trim()])));
}

function toE164(phone) {
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10) return `+1${digits}`;
  if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`;
  return null;
}

// Direct-download link Twilio can fetch. The Drive file must be shared "Anyone with the link".
const driveMediaUrl = (id) => `https://drive.google.com/uc?export=download&id=${encodeURIComponent(id)}`;

const norm = (s) => s.toLowerCase().replace(/\s+/g, ' ').trim();

const coaches = parseCsv(coachesPath);
const posts = parseCsv(postsPath);

const messages = [];
for (const coach of coaches) {
  const to = toE164(coach.phone || '');
  if (norm(coach.consent || '') !== 'yes') { console.warn(`skip ${coach.name}: no SMS consent`); continue; }
  if (!to) { console.warn(`skip ${coach.name}: bad phone "${coach.phone}"`); continue; }
  for (const post of posts.filter((p) => norm(p.team) === norm(coach.team))) {
    const first = coach.name.split(' ')[0] || 'Coach';
    const body = `Hi Coach ${first}! ${post.caption || `Here's a ${coach.team} post from Elite 32.`}\nReply STOP to opt out.`;
    messages.push({ to, coach: coach.name, team: coach.team, body, mediaUrl: driveMediaUrl(post.drive_file_id) });
  }
}

const teamsWithCoach = new Set(coaches.map((c) => norm(c.team)));
for (const p of posts) if (!teamsWithCoach.has(norm(p.team))) console.warn(`no coach for team "${p.team}" (${p.drive_file_id})`);

console.log(`${messages.length} message(s) ${send ? 'to send' : '(dry run — add --send to send)'}\n`);

if (!send) {
  for (const m of messages) console.log(`→ ${m.coach} ${m.to} [${m.team}]\n  ${m.mediaUrl}\n  ${m.body.replace(/\n/g, '\n  ')}\n`);
  process.exit(0);
}

const { TWILIO_ACCOUNT_SID: sid, TWILIO_AUTH_TOKEN: token, TWILIO_FROM_NUMBER: from } = process.env;
if (!sid || !token || !from) {
  console.error('Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER.');
  process.exit(1);
}

const auth = 'Basic ' + Buffer.from(`${sid}:${token}`).toString('base64');
let failed = 0;
for (const m of messages) {
  const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
    method: 'POST',
    headers: { Authorization: auth, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ To: m.to, From: from, Body: m.body, MediaUrl: m.mediaUrl }),
  });
  const data = await res.json();
  if (res.ok) console.log(`sent  ${m.coach} ${m.to} ${data.sid}`);
  else { failed++; console.error(`FAIL  ${m.coach} ${m.to}: ${data.code} ${data.message}`); }
  await new Promise((r) => setTimeout(r, 1100)); // stay under ~1 msg/sec on a 10DLC number
}
process.exit(failed ? 1 : 0);
