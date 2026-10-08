# Amy's Closet: getting live

## 1. The website (free)
This repo is a one-page site (`index.html`) hosted free on GitHub Pages.

1. In GitHub, open **Settings → Pages** and set **Source** to **GitHub Actions** (one time only).
2. Every push runs `.github/workflows/pages.yml`, which publishes the site.
3. Open `index.html`, find the `EDIT THESE LINKS` block near the bottom, and paste in the
   Instagram and Depop shop URLs. Facebook is already filled in.
5. The Lister saves to the branch named in its Settings. If the site later moves to `main`, change it there.
4. Optional: attach a custom domain such as amyscloset.com (about $12/yr) under **Settings → Pages**.

## 2. Selling: Depop handles the money
Buyers pay through **Depop**. Depop takes the payment, covers buyer protection and gives you prepaid
shipping labels. It pays you the sale price minus processing (3.3% + $0.45). US sellers pay no selling fee.
Local buyers can still message on Facebook and pay in the store.

The website doesn't embed Depop. It shows each item itself, and the **Buy on Depop** button opens
that listing. Items without a Depop link show **Message to buy** instead, which opens Facebook.

## 3. Adding items: the Lister (`admin.html`)
Open `https://legal-leaf-market.github.io/amyscloset/admin.html` on the shop phone. Bookmark it or add it to the home screen.

**Each new item:**
1. List it on Depop. Then tap Share, then Copy link.
2. In the Lister: take or pick a photo, then enter the name, size, price and Depop link.
3. Tick Post to Facebook and/or Post to Instagram, then tap **List it**.
4. It appears on the website in 1–2 minutes. Instagram posts once the photo is live.

**When something sells:** tap **Mark sold** and it disappears from the website. You can also
add a Depop link to an older item from the same list.

### One-time setup (about 30 minutes)
Everything below is saved only on the phone that uses the Lister. Never paste these keys anywhere else.

**A. GitHub key**, which lets the Lister update the website:
1. github.com, then Settings, then Developer settings, then Personal access tokens, then **Fine-grained tokens**, then Generate.
2. Repository access: *Only select repositories* → `amyscloset`.
3. Permissions: **Contents → Read and write**. Expiration: up to 1 year.
4. Copy the token into Lister → Settings → GitHub key, then tap Save.

**B. Instagram account**
1. Create the account, for example @amyscloset. Then go to Settings, then Account type, then switch to **Business**.
2. Link it to the Facebook Page: Meta Business Suite, then Settings, then Linked accounts, then Instagram.
3. Bio: "Clothing thrift shop in Columbus, IN. Donated clothes, triple inspected. 10% of every sale
   goes to Love Chapel's food pantry. Resellers welcome." Put the website or Depop shop as the bio link.

**C. Facebook and Instagram posting keys** (optional; skip this to post by hand):
1. Go to developers.facebook.com, then My Apps, then Create app, then Other, then **Business**. Name it "Amy's Closet Lister".
2. Add the products **Facebook Login for Business** and **Instagram**.
3. Open **Tools, then Graph API Explorer**, pick the app, then *Get Page Access Token*. Grant
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic` and
   `instagram_content_publish`, and select the Amy's Closet Page.
4. Turn it into a long-lived token. Use the Access Token Debugger, then **Extend Access Token**. Then call
   `GET /me/accounts` with the extended token. The `access_token` shown next to the Page is a
   Page token that doesn't expire. Paste it into Settings as the Page access token, and paste `id` as the Page ID.
5. Call `GET /{page-id}?fields=instagram_business_account`. Paste that `id` as the Instagram account ID.
6. The app can stay in development mode, because it only posts to your own Page and account.

Instagram captions can't hold clickable links, so posts say "link in bio." Facebook posts include the Depop link.

## 4. Things to confirm before launch
- The drop-off location and hours. The site currently says "message us on Facebook."
- Sizes and prices for the Ghost Face sweatshirt and the Diamondback tee. Use Lister, then Remove, then re-add, or edit `products.json`.
- That Love Chapel is fine with being named. They list their phone as 812-372-9421.
