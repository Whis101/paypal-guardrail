// Locate a full ffmpeg build (winget installs it under WinGet\Links or Packages).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

export function ffmpeg(name = 'ffmpeg') {
  if (process.env.FFMPEG && name === 'ffmpeg') return process.env.FFMPEG;
  try {
    execFileSync(name, ['-version'], { stdio: 'ignore' });
    return name;
  } catch { /* not on PATH in this shell */ }
  const local = process.env.LOCALAPPDATA || '';
  const link = path.join(local, 'Microsoft', 'WinGet', 'Links', `${name}.exe`);
  if (fs.existsSync(link)) return link;
  const pkgs = path.join(local, 'Microsoft', 'WinGet', 'Packages');
  if (fs.existsSync(pkgs)) {
    for (const d of fs.readdirSync(pkgs).filter((d) => d.startsWith('Gyan.FFmpeg'))) {
      const stack = [path.join(pkgs, d)];
      while (stack.length) {
        const dir = stack.pop();
        for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
          const p = path.join(dir, e.name);
          if (e.isDirectory()) stack.push(p);
          else if (e.name === `${name}.exe`) return p;
        }
      }
    }
  }
  throw new Error(`${name} not found. Install with: winget install Gyan.FFmpeg`);
}
