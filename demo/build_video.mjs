// Turns out/raw.webm + out/timeline.json into:
//   out/teleprompter.mp4  countdown + current line + grey preview of the next line (read along to this)
//   out/captioned.mp4     countdown trimmed, clean one-line captions (your audio is merged onto this)
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { ffmpeg } from './ffmpeg.mjs';

const OUT = path.resolve('out');
const tl = JSON.parse(fs.readFileSync(path.join(OUT, 'timeline.json'), 'utf8'));
const SEC_PER_WORD = 60 / tl.wpm;

function chunk(text) {
  const out = [];
  let cur = [];
  for (const w of text.trim().split(/\s+/)) {
    cur.push(w);
    const n = cur.length;
    if (n >= 10 || (/[.?!:]$/.test(w) && n >= 3) || (/,$/.test(w) && n >= 6)) {
      out.push(cur); cur = [];
    }
  }
  if (cur.length) out.push(cur);
  return out;
}

// Caption cues: each line appears when you should start saying it, at a steady pace.
const cues = [];
for (const s of tl.scenes) {
  const chunks = chunk(s.text);
  let t = s.start;
  chunks.forEach((words, i) => {
    const end = i === chunks.length - 1 ? s.end : t + words.length * SEC_PER_WORD;
    cues.push({ start: t, end, text: words.join(' ') });
    t = end;
  });
}

const ts = (sec) => {
  sec = Math.max(0, sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return `${h}:${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`;
};
const esc = (t) => t.replace(/[{}]/g, '').replace(/\\/g, '');

const header = `[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Segoe UI,34,&H00FFFFFF,&H00FFFFFF,&HB4000000,&HB4000000,1,0,0,0,100,100,0,0,3,10,0,2,60,60,40,1
Style: Next,Segoe UI,24,&H00B4B4B4,&H00B4B4B4,&HB4000000,&HB4000000,0,0,0,0,100,100,0,0,3,8,0,2,60,60,6,1
Style: Big,Segoe UI,72,&H00FFFFFF,&H00FFFFFF,&HB4000000,&HB4000000,1,0,0,0,100,100,0,0,3,24,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;
const ev = (start, end, style, text) =>
  `Dialogue: 0,${ts(start)},${ts(end)},${style},,0,0,0,,${esc(text)}\n`;

// Teleprompter: countdown on screen, then current line + preview of the next one.
let tele = header;
const cd = tl.countdown;
const n = Math.round(cd.end - cd.start);
for (let i = 0; i < n; i++) {
  const s = cd.start + i;
  tele += ev(s, s + 1, 'Big', i < n - 3 ? 'Get ready to read' : String(n - i));
}
cues.forEach((c, i) => {
  tele += ev(c.start, c.end, 'Cap', c.text);
  if (cues[i + 1]) tele += ev(c.start, c.end, 'Next', `next: ${cues[i + 1].text}`);
});
// Final: shifted so the video starts right where narration starts.
const shift = cd.end;
let final = header;
for (const c of cues) final += ev(c.start - shift, c.end - shift, 'Cap', c.text);

fs.writeFileSync(path.join(OUT, 'teleprompter.ass'), tele);
fs.writeFileSync(path.join(OUT, 'final.ass'), final);

const enc = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30'];
// Run inside out/ so the ass filter gets a plain relative filename (Windows paths break it).
const run = (args) => execFileSync(ffmpeg(), ['-y', '-hide_banner', '-loglevel', 'error', ...args], { cwd: OUT, stdio: 'inherit' });

run(['-i', 'raw.webm', '-vf', 'ass=teleprompter.ass', ...enc, '-an', 'teleprompter.mp4']);
run(['-ss', shift.toFixed(3), '-i', 'raw.webm', '-vf', 'ass=final.ass', ...enc, '-an', 'captioned.mp4']);

const finalLen = tl.total - shift;
console.log(`teleprompter.mp4: ${tl.total.toFixed(1)}s (incl. ${n}s countdown)`);
console.log(`captioned.mp4:    ${finalLen.toFixed(1)}s ${finalLen > 178 ? '!! OVER 3:00 LIMIT' : '(under 3:00)'}`);
console.log(`pace: ${tl.wpm} words/min, ${cues.length} caption lines`);
