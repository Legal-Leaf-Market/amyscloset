# Facebook scraper for Amy's Closet

Runs on your own computer (Mac or Windows), in a real browser where you're logged in to Facebook.
It saves every photo post from the last 45 days: the full-size photo, the caption and the date.

## One-time setup
1. Install Node.js (the LTS version) from https://nodejs.org.
2. Open a terminal in this folder (`tools/fb-scrape`) and run:
   ```
   npm install
   npx playwright install chromium
   ```

## Run it
```
npm run scrape
```
- A browser window opens. Log in to Facebook the first time. The login is remembered in `browser-profile/`.
- Leave the window alone while it scrolls the Photos tab and opens each photo. Expect 1–2 seconds per photo.
- Options: `npm run scrape -- --days 90 --max 400`
- If it stops partway, run it again. It skips photos it already saved.

## Then
Zip the `out` folder and send it. The photos get matched to the items on the site,
and any new pieces get added with names, sizes and prices read from the photos and tags.

Keep `browser-profile/` private. It holds your Facebook login. It's excluded from git.
