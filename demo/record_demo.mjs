// Drives the real Guardrail UI in Chromium and records it to video.
// Each scene is held until its narration would finish at WPM, and the real start time of
// every scene is written to out/timeline.json so captions line up with the footage.
//
// Prereqs: backend on :8000 and frontend on :5173 running.  Usage: node record_demo.mjs
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { SCENES, COUNTDOWN_SECONDS, speechSeconds, WPM } from './scenes.mjs';

const APP = process.env.APP_URL || 'http://localhost:5173';
const OUT = path.resolve('out');
const SIZE = { width: 1280, height: 720 };
const PAD = 0.9; // breathing room after each scene's narration (seconds)

fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) if (f.endsWith('.webm')) fs.rmSync(path.join(OUT, f));

// A visible cursor: headless recordings don't draw the mouse pointer.
const CURSOR_JS = `
  window.addEventListener('DOMContentLoaded', () => {
    const c = document.createElement('div');
    c.id = '__demo_cursor';
    Object.assign(c.style, {position:'fixed', left:'0px', top:'0px', width:'22px', height:'22px',
      marginLeft:'-11px', marginTop:'-11px', borderRadius:'50%', background:'rgba(0,112,224,.35)',
      border:'2px solid #0070e0', zIndex:2147483647, pointerEvents:'none',
      transition:'transform .12s ease', boxShadow:'0 0 0 4px rgba(255,255,255,.6)'});
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX+'px'; c.style.top = e.clientY+'px'; }, true);
    document.addEventListener('mousedown', () => c.style.transform = 'scale(.7)', true);
    document.addEventListener('mouseup',   () => c.style.transform = 'scale(1)',  true);
  });`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let mouse = { x: 640, y: 360 };

async function moveTo(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y, { steps: 25 });
  mouse = { x, y };
  await sleep(250);
}
async function click(page, locator) {
  await moveTo(page, locator);
  await page.mouse.down(); await sleep(90); await page.mouse.up();
}
async function type(page, locator, text) {
  await click(page, locator);
  await locator.pressSequentially(text, { delay: 45 });
}
const tab = (page, name) => page.getByRole('tab', { name, exact: true });

async function runAgent(page, mandate) {
  const box = page.getByPlaceholder('Restock household essentials for a family of four');
  await box.fill('');
  if (mandate) await type(page, box, mandate);
  const resp = page.waitForResponse((r) => r.url().endsWith('/api/agent/run'), { timeout: 60_000 });
  await click(page, page.getByRole('button', { name: 'Run shopping agent' }));
  const tx = await (await resp).json();
  if (!tx.id) throw new Error(`Agent run failed: ${JSON.stringify(tx)}`);
  await page.locator('.result').first().waitFor();
  await moveTo(page, page.locator('.result').first());
  return tx;
}

const money = (c) => (c / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' });

const ACTIONS = {
  async intro(page) {
    await moveTo(page, page.getByRole('button', { name: 'Run shopping agent' }));
  },
  async rules(page) {
    await click(page, tab(page, 'Rules'));
    await sleep(800);
    const rows = page.locator('table tbody tr');
    const n = await rows.count();
    for (let i = 0; i < n; i++) { await moveTo(page, rows.nth(i)); await sleep(1100); }
  },
  async 'run-small'(page, ctx) {
    await click(page, tab(page, 'Dashboard'));
    ctx.small = await runAgent(page, 'Restock pantry basics for the week');
  },
  async 'result-small'(page) {
    for (const sel of ['.result-amount', '.result-grid', '.result a']) {
      const l = page.locator(sel).first();
      if (await l.count()) { await moveTo(page, l); await sleep(1500); }
    }
  },
  async 'run-big'(page, ctx) {
    ctx.big = await runAgent(page, 'My kid needs a new laptop for school this week.');
    const reason = page.locator('.result').first().getByText(/exceeds|over the/).first();
    if (await reason.count()) await moveTo(page, reason);
  },
  async approve(page, ctx) {
    await click(page, tab(page, 'Approvals'));
    const card = page.locator('.approval-card').filter({ hasText: money(ctx.big.amount_cents) }).first();
    await card.waitFor();
    await moveTo(page, card);
    await sleep(1800);
    await click(page, card.getByRole('button', { name: /Approve/ }));
    await page.waitForResponse((r) => r.url().includes('/decision'), { timeout: 60_000 });
    await sleep(600);
  },
  async grid(page) {
    await click(page, tab(page, 'Transactions'));
    await page.locator('.ag-row').first().waitFor();
    await sleep(1500);
    await type(page, page.getByPlaceholder(/Search merchant/), 'captured');
    await sleep(2200);
    await page.getByPlaceholder(/Search merchant/).fill('');
    await sleep(600);
    await click(page, page.locator('.ag-header-cell', { hasText: 'Amount' }).first());
    await sleep(1800);
    const link = page.locator('.ag-row a').first();
    if (await link.count()) await moveTo(page, link);
  },
  async outro(page) {
    await click(page, tab(page, 'Dashboard'));
    await sleep(500);
    await page.mouse.move(640, 120, { steps: 30 });
  },
};

// LIVE=1: drive your installed Chrome in a visible app window and draw captions in the
// page itself (they double as a teleprompter); you screen-record it with Win+Alt+R.
// Otherwise: headless recording to out/raw.webm, captions burned in later by ffmpeg.
const LIVE = process.env.LIVE === '1';

// On-page captions: current line large, next line small and grey (teleprompter preview).
const CAPTION_JS = `
  window.__showCaption = (text, next, big) => {
    let box = document.getElementById('__demo_cap');
    if (!box) {
      box = document.createElement('div'); box.id = '__demo_cap';
      Object.assign(box.style, {position:'fixed', left:'50%', bottom:'28px', transform:'translateX(-50%)',
        maxWidth:'1100px', width:'max-content', textAlign:'center', zIndex:2147483646, pointerEvents:'none',
        fontFamily:'Segoe UI, system-ui, sans-serif'});
      document.body.appendChild(box);
    }
    box.style.bottom = big ? '45%' : '28px';
    box.replaceChildren();
    if (!text) return;
    const cur = document.createElement('div');
    cur.textContent = text;
    Object.assign(cur.style, {background:'rgba(0,0,0,.78)', color:'#fff', fontWeight:'600',
      fontSize: big ? '64px' : '30px', lineHeight:'1.3', padding:'10px 22px', borderRadius:'10px'});
    box.appendChild(cur);
    if (next) {
      const n = document.createElement('div');
      n.textContent = 'next: ' + next;
      Object.assign(n.style, {marginTop:'6px', background:'rgba(0,0,0,.55)', color:'#bbb',
        fontSize:'20px', padding:'4px 14px', borderRadius:'8px', display:'inline-block'});
      box.appendChild(n);
    }
  };`;

function chunkText(text) {
  const out = []; let cur = [];
  for (const w of text.trim().split(/\s+/)) {
    cur.push(w);
    const n = cur.length;
    if (n >= 10 || (/[.?!:]$/.test(w) && n >= 3) || (/,$/.test(w) && n >= 6)) { out.push(cur.join(' ')); cur = []; }
  }
  if (cur.length) out.push(cur.join(' '));
  return out;
}

// Schedule a scene's caption lines at a steady speaking pace (runs alongside the clicks).
function playCaptions(page, text, nextSceneText) {
  const lines = chunkText(text);
  const firstOfNext = nextSceneText ? chunkText(nextSceneText)[0] : '';
  let at = 0;
  const timers = lines.map((line, i) => {
    const t = setTimeout(() => {
      page.evaluate(([a, b]) => window.__showCaption?.(a, b, false), [line, lines[i + 1] ?? firstOfNext]).catch(() => {});
    }, at * 1000);
    at += (line.split(/\s+/).length * 60) / WPM;
    return t;
  });
  return () => timers.forEach(clearTimeout);
}

let context, page;
if (LIVE) {
  context = await chromium.launchPersistentContext(path.join(OUT, 'chrome-profile'), {
    channel: 'chrome', headless: false, viewport: null,
    args: [`--app=${APP}`, '--window-size=1296,800', '--window-position=40,40'],
    ignoreDefaultArgs: ['--enable-automation'],
  });
  await context.addInitScript(CURSOR_JS);
  await context.addInitScript(CAPTION_JS);
  page = context.pages()[0] ?? (await context.newPage());
  await page.reload();
} else {
  const browser = await chromium.launch();
  context = await browser.newContext({ viewport: SIZE, deviceScaleFactor: 1, recordVideo: { dir: OUT, size: SIZE } });
  await context.addInitScript(CURSOR_JS);
  page = await context.newPage();
}
const t0 = Date.now(); // video timeline starts when the page is created
const now = () => (Date.now() - t0) / 1000;

if (!LIVE) await page.goto(APP);
await page.getByRole('button', { name: 'Run shopping agent' }).waitFor();
await page.mouse.move(mouse.x, mouse.y);

const timeline = { wpm: WPM, countdown: { start: now(), end: 0 }, scenes: [] };
if (LIVE) {
  console.log('Chrome is open. Start recording now: click the Guardrail window, press Win+Alt+R (mic on).');
  const big = (t) => page.evaluate((x) => window.__showCaption(x, '', true), t);
  await big('Start recording: Win + Alt + R'); await sleep(10000);
  for (const n of ['3', '2', '1']) { await big(n); await sleep(1000); }
  await page.evaluate(() => window.__showCaption(''));
} else {
  await sleep(COUNTDOWN_SECONDS * 1000);
}
timeline.countdown.end = now();

const ctx = {};
for (const [i, scene] of SCENES.entries()) {
  const start = now();
  process.stdout.write(`[${start.toFixed(1)}s] ${scene.id} ... `);
  const stopCaptions = LIVE ? playCaptions(page, scene.text, SCENES[i + 1]?.text) : () => {};
  await ACTIONS[scene.id](page, ctx);
  const target = start + speechSeconds(scene.text) + PAD;
  const wait = target - now();
  if (wait > 0) await sleep(wait * 1000);
  stopCaptions();
  const end = now();
  timeline.scenes.push({ id: scene.id, text: scene.text, start, end });
  console.log(`${(end - start).toFixed(1)}s${wait < 0 ? `  (action ran ${(-wait).toFixed(1)}s past narration)` : ''}`);
}
await sleep(1500);
timeline.total = now();

if (LIVE) {
  await page.evaluate(() => window.__showCaption('Done. Stop recording: Win + Alt + R', '', true));
  await sleep(6000);
  await context.close();
  fs.writeFileSync(path.join(OUT, 'timeline.json'), JSON.stringify({ ...timeline, small: ctx.small, big: ctx.big }, null, 2));
  console.log(`\nLive run done: ${(timeline.total - timeline.countdown.end).toFixed(1)}s of narration footage.`);
  process.exit(0);
}

const videoPath = await page.video().path();
await context.close();
await browser.close();
fs.renameSync(videoPath, path.join(OUT, 'raw.webm'));
fs.writeFileSync(path.join(OUT, 'timeline.json'), JSON.stringify({ ...timeline, small: ctx.small, big: ctx.big }, null, 2));
console.log(`\nRecorded ${timeline.total.toFixed(1)}s -> out/raw.webm, out/timeline.json`);
