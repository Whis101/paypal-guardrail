// Merges your narration onto out/captioned.mp4 -> out/guardrail_demo.mp4
// Usage: node merge_audio.mjs <your-recording.m4a|mp3|wav> [extra-offset-seconds]
//
// You start recording, then press play on the teleprompter; so the recording has some
// lead-in. We detect when you first start speaking and line that up with the first caption.
// If it's slightly off, pass an offset: positive = voice later, negative = voice earlier.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { ffmpeg } from './ffmpeg.mjs';

const [, , audioArg, offsetArg] = process.argv;
if (!audioArg || !fs.existsSync(audioArg)) {
  console.error('Usage: node merge_audio.mjs <audio file> [offset seconds]');
  process.exit(1);
}
const audio = path.resolve(audioArg);
const OUT = path.resolve('out');
const tl = JSON.parse(fs.readFileSync(path.join(OUT, 'timeline.json'), 'utf8'));
const FF = ffmpeg();

const duration = (file) => {
  const r = spawnSync(FF, ['-hide_banner', '-i', file], { encoding: 'utf8' });
  const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(r.stderr);
  return m ? +m[1] * 3600 + +m[2] * 60 + +m[3] : NaN;
};

// First moment the recording rises above the noise floor = when you start talking.
const sd = spawnSync(FF, ['-hide_banner', '-i', audio, '-af', 'silencedetect=noise=-38dB:d=0.4', '-f', 'null', '-'],
  { encoding: 'utf8' });
const firstEnd = /silence_end: ([\d.]+)/.exec(sd.stderr);
const startsWithSilence = /silence_start: (0|0\.0\d*|-)/.test(sd.stderr);
const speechOnset = firstEnd && startsWithSilence ? Number(firstEnd[1]) : 0;

const firstCaption = tl.scenes[0].start - tl.countdown.end; // in captioned.mp4 time (~0)
const extra = Number(offsetArg || 0);
// Seek the audio so speech onset lands on the first caption (+ any manual nudge).
const audioSeek = speechOnset - firstCaption - extra;

const vLen = duration(path.join(OUT, 'captioned.mp4'));
const aLen = duration(audio) - Math.max(0, audioSeek);
const hold = Math.max(0, aLen - vLen + 0.5); // if you ran long, freeze the last frame

const args = ['-y', '-hide_banner', '-loglevel', 'error', '-i', 'captioned.mp4'];
if (audioSeek >= 0) args.push('-ss', audioSeek.toFixed(3), '-i', audio);
else args.push('-itsoffset', (-audioSeek).toFixed(3), '-i', audio);
args.push(
  '-filter_complex',
  `[0:v]tpad=stop_mode=clone:stop_duration=${hold.toFixed(2)}[v];` +
    '[1:a]highpass=f=80,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad[a]',
  '-map', '[v]', '-map', '[a]', '-t', (vLen + hold).toFixed(2),
  '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30',
  '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
  'guardrail_demo.mp4',
);
execFileSync(FF, args, { cwd: OUT, stdio: 'inherit' });

const total = duration(path.join(OUT, 'guardrail_demo.mp4'));
console.log(`speech detected at ${speechOnset.toFixed(2)}s in your recording; aligned to first caption`);
if (hold > 0) console.log(`you ran ${hold.toFixed(1)}s past the footage; last frame held to fit`);
console.log(`out/guardrail_demo.mp4: ${total.toFixed(1)}s ${total > 179 ? '!! OVER 3:00, trim or re-record faster' : '(under 3:00)'}`);
