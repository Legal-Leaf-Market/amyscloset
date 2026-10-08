# Amy's Closet: getting live

## 1. The website (free)
This repo is a one-page site (`index.html`) hosted free on GitHub Pages.

1. In GitHub, open **Settings → Pages** and set **Source** to **GitHub Actions** (one time only).
2. Every push runs `.github/workflows/pages.yml`, which publishes the site.
3. Open `index.html`, find the `EDIT THESE LINKS` block near the bottom, and paste in the real
   Facebook, Instagram and online-store URLs. Until you do, the buttons go to a Facebook search.
4. Optional: attach a custom domain such as amyscloset.com (about $12/yr) under **Settings → Pages**.

## 2. Payments: how Instagram works now
Instagram and Facebook Shops **no longer take payment for you**. Meta shut down checkout
on Facebook and Instagram in September 2025. Shops now send buyers to *your own* online store to pay.
So you need a store that takes the card payment and pays you out.

**Recommended: Square Online, free plan**
- $0/month. You pay only a processing fee on each sale, which comes out of the payout automatically.
- Square takes the card payment and deposits the money to your bank.
- It connects to Facebook and Instagram. You list each item once in Square, and it syncs to the
  Facebook Shop and Instagram Shop so you can tag items in posts.
- Shopify isn't free (it costs a monthly fee). Square is the closest free option.

Steps:
1. Sign up at squareup.com and create the Square Online site (free plan).
2. Add each item with photos, size and price. Use quantity 1, since every piece is one-of-a-kind.
3. In Square, turn on the **Facebook & Instagram** sales channel. That sets up the Meta catalog.
4. Paste the Square store URL into `LINKS.store` in `index.html`.

## 3. Instagram
1. Create the account, for example @amyscloset, and switch it to a **Business** account.
2. Link it to the existing Facebook Page (Meta Business Suite → Settings → Linked accounts).
3. In Commerce Manager, connect the Square catalog and submit the shop for review. Review takes a few days.
4. Once it's approved, tag products in each post. One post per item works best for individual pieces.
5. Bio: "Donated clothes, triple inspected. 10% of every sale feeds families through Love Chapel 🍞 Resellers welcome."
6. Paste the Instagram URL into `LINKS.instagram`.

## 4. Things to confirm before launch
- The drop-off location and hours. The site currently says "message us on Facebook."
- That Love Chapel is fine with being named. They list their phone as 812-372-9421.
