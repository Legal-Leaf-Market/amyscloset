# Amy's Closet: getting live

## 1. The website (free)
This repo is a one-page site (`index.html`) hosted free on GitHub Pages.

1. In GitHub, open **Settings → Pages** and set **Source** to **GitHub Actions** (one time only).
2. Every push runs `.github/workflows/pages.yml`, which publishes the site.
3. Open `index.html`, find the `EDIT THESE LINKS` block near the bottom, and paste in the real
   Facebook, Instagram and online-store URLs. Until you do, the buttons go to a Facebook search.
4. Optional: attach a custom domain such as amyscloset.com (about $12/yr) under **Settings → Pages**.

## 2. Payments: let a marketplace handle the money
Goal: no card processing and no chargeback risk. Buyers pay a third party, and that third party
pays you the total minus its cut.

**Recommended: Vinted (you already sell there)**
- Vinted collects payment, covers buyer protection and disputes, gives you prepaid shipping labels,
  and releases the money to your balance once the buyer confirms. US sellers pay **no selling fee**.
  The buyer pays a protection fee instead.
- **Don't open a second account.** Vinted's rules allow one account per person, and duplicate
  accounts get banned (vinted.com/help/1436). Put *all* items in the account you already have.
  If Amy's Closet is a registered business, ask Vinted whether a business/Pro account is available
  in the US. That's the legitimate way to run a separate store.
- Paste the Vinted closet URL into `LINKS.store` in `index.html`. The "Shop online" button then goes there.

**Instagram / Facebook with a marketplace**
- Meta ended in-app checkout in Sept 2025. Shops now must send buyers to a website *you own*,
  so an Instagram Shop can't point at Vinted. Instead, post each item on Instagram/Facebook with
  "Shop it on Vinted, link in bio" and put the Vinted (or website) link in the bio.
- Facebook Marketplace: local pickup listings stay free and simple (cash/meet-up).

**Other hands-off marketplaces, if you ever want more reach:** Poshmark, Mercari, Depop and eBay
all collect payment and pay out minus a commission (typically ~10–20%). Crosslisting tools such as
Vendoo or List Perfectly can post one item to several of them at once.

**If you later want checkout on your own site:** Square Online's free plan has no monthly fee and takes
a per-sale processing fee. You'd be the merchant, though, so disputes and chargebacks come to you.

## 3. Instagram
1. Create the account, for example @amyscloset, and switch it to a **Business** account.
2. Link it to the existing Facebook Page (Meta Business Suite → Settings → Linked accounts).
3. Post one photo set per item, with size, price and "Shop on Vinted, link in bio."
4. Bio: "Donated clothes, triple inspected. 10% of every sale feeds families through Love Chapel. Resellers welcome."
5. Paste the Instagram URL into `LINKS.instagram`.

## 4. Things to confirm before launch
- The drop-off location and hours. The site currently says "message us on Facebook."
- That Love Chapel is fine with being named. They list their phone as 812-372-9421.
