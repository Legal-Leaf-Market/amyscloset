// Scrapes photo posts from the Amy's Closet Facebook page using a real browser window.
//
//   npm install && npx playwright install chromium
//   npm run scrape                      # last 45 days, opens a browser window
//   npm run scrape -- --days 90 --max 400
//
// The first run opens Facebook so you can log in. The login is saved in ./browser-profile
// (keep that folder private; it's in .gitignore). Output goes to ./out:
//   out/images/<fbid>.jpg   full-size photos
//   out/posts.json          [{ fbid, url, caption, posted, image }]
// Then zip the out folder and send it over to be matched to the site's items.

import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const PAGE_ID = "100091049706849";
const args = Object.fromEntries(process.argv.slice(2).join(" ").split("--").filter(Boolean)
  .map((a) => a.trim().split(/\s+/)).map(([k, v]) => [k, v ?? true]));
const DAYS = Number(args.days ?? 45);
const MAX = Number(args.max ?? 300);
const OUT = path.resolve("out");
const since = new Date(Date.now() - DAYS * 864e5);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jitter = (ms) => sleep(ms + Math.random() * ms); // be gentle with Facebook

await fs.mkdir(path.join(OUT, "images"), { recursive: true });
const ctx = await chromium.launchPersistentContext(path.resolve("browser-profile"), {
  headless: false, viewport: { width: 1280, height: 900 },
});
const page = ctx.pages()[0] ?? (await ctx.newPage());

// 1. Make sure we're logged in.
await page.goto("https://www.facebook.com/");
if (await page.locator('input[name="email"]').count()) {
  console.log("\nLog in to Facebook in the browser window. Waiting up to 5 minutes…\n");
  await page.waitForSelector('input[name="email"]', { state: "detached", timeout: 300_000 });
  await sleep(3000);
}

// 2. Collect photo links from the page's Photos tab, scrolling until we have enough.
await page.goto(`https://www.facebook.com/profile.php?id=${PAGE_ID}&sk=photos_by`);
await sleep(4000);
const links = new Map();
let stale = 0;
while (links.size < MAX && stale < 6) {
  const before = links.size;
  const found = await page.$$eval('a[href*="/photo"]', (as) => as.map((a) => a.href));
  for (const href of found) {
    const m = /[?&]fbid=(\d+)/.exec(href) || /\/photos\/[^/]+\/(\d+)/.exec(href);
    if (m && !links.has(m[1])) links.set(m[1], href);
  }
  stale = links.size === before ? stale + 1 : 0;
  await page.mouse.wheel(0, 2500);
  await jitter(1200);
}
console.log(`Found ${links.size} photos. Reading each one…`);

// 3. Visit each photo: grab the full-size image, caption and date.
let existing = [];
try { existing = JSON.parse(await fs.readFile(path.join(OUT, "posts.json"), "utf8")); } catch {}
const done = new Set(existing.map((p) => p.fbid));
const posts = [...existing];
let tooOld = 0;

for (const [fbid, href] of links) {
  if (done.has(fbid)) continue;
  try {
    await page.goto(`https://www.facebook.com/photo/?fbid=${fbid}`, { waitUntil: "domcontentloaded" });
    await jitter(1500);
    const info = await page.evaluate(() => {
      // Largest image on the page is the photo itself.
      const imgs = [...document.querySelectorAll("img")].filter((i) => /fbcdn|scontent/.test(i.src));
      imgs.sort((a, b) => b.naturalWidth * b.naturalHeight - a.naturalWidth * a.naturalHeight);
      const img = imgs[0]?.src || document.querySelector('meta[property="og:image"]')?.content || "";
      // Caption: og:description when present, else the longest short text block near the photo.
      let caption = document.querySelector('meta[property="og:description"]')?.content || "";
      if (!caption) {
        const texts = [...document.querySelectorAll('div[dir="auto"], span[dir="auto"]')]
          .map((e) => e.innerText.trim()).filter((t) => t.length > 8 && t.length < 600 && !/^(Like|Comment|Share|Write a comment)/.test(t));
        caption = texts.sort((a, b) => b.length - a.length)[0] || "";
      }
      // Date: Facebook puts the full timestamp in a tooltip/aria-label on the time link.
      const timeEl = [...document.querySelectorAll("a[aria-label], span[aria-label], abbr[title]")]
        .map((e) => e.getAttribute("aria-label") || e.getAttribute("title") || "")
        .find((t) => /\b(January|February|March|April|May|June|July|August|September|October|November|December)\b.*\d{4}/.test(t)
          || /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/.test(t));
      return { img, caption, timeText: timeEl || "" };
    });
    const posted = info.timeText ? new Date(info.timeText.replace(/ at /, " ")) : null;
    const postedIso = posted && !isNaN(posted) ? posted.toISOString().slice(0, 10) : "";
    if (posted && !isNaN(posted) && posted < since) { if (++tooOld >= 8) break; continue; }

    let image = "";
    if (info.img) {
      const res = await page.request.get(info.img);
      if (res.ok()) {
        image = `images/${fbid}.jpg`;
        await fs.writeFile(path.join(OUT, image), await res.body());
      }
    }
    posts.push({ fbid, url: href, caption: info.caption, posted: postedIso, image });
    await fs.writeFile(path.join(OUT, "posts.json"), JSON.stringify(posts, null, 2));
    console.log(`${posts.length}. ${postedIso || "?"}  ${image ? "photo saved" : "NO PHOTO"}  ${info.caption.slice(0, 60)}`);
  } catch (e) {
    console.log(`Skipped ${fbid}: ${e.message.split("\n")[0]}`);
  }
}

await ctx.close();
console.log(`\nDone. ${posts.length} posts in ${OUT}. Zip the "out" folder and send it over.`);
