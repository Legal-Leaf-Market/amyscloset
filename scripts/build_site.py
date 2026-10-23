"""Build the per-item pages and the Meta (Facebook/Instagram) catalog feed from products.json.

Runs in the Pages deploy (.github/workflows/pages.yml) right before upload, so every deploy,
including the one the Facebook sync triggers, publishes a fresh feed. Nothing it writes is committed.

Outputs:
  items/<id>.html          one page per item: photo, price, size, buy button, Open Graph + schema.org tags
  feeds/meta-catalog.csv   Meta catalog data feed (Commerce Manager > Catalog > Data sources > scheduled feed)
  checkout.html            target for Meta's "checkout URL"; forwards to the item's page

Sold items stay in the feed as "out of stock" for 30 days after they sell, then drop out.
sold.json (optional) is a list of item ids to treat as sold without editing products.json.

Env:
  SITE_URL   absolute site address ending in "/", e.g. https://legal-leaf-market.github.io/amyscloset/
"""
import csv
import html
import json
import os
import re
import sys
from datetime import date, timedelta

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = os.environ.get("SITE_URL", "https://legal-leaf-market.github.io/amyscloset/").rstrip("/") + "/"
FACEBOOK = "https://www.facebook.com/profile.php?id=100091049706849"
SOLD_KEEP_DAYS = 30
BRAND = "Amy's Closet"

FEED_COLUMNS = ["id", "title", "description", "availability", "condition", "price", "link", "image_link",
                "additional_image_link", "brand", "google_product_category", "size", "color", "gender",
                "age_group"]

# Google product taxonomy ids (Meta accepts these): Apparel & Accessories, Clothing, Shoes.
GOOGLE_CATEGORY = {"Shoes": "187", "Accessories": "166"}
CLOTHING = "1604"


def load_items():
    items = json.load(open(os.path.join(ROOT, "products.json")))
    sold_path = os.path.join(ROOT, "sold.json")
    if os.path.exists(sold_path):
        forced = set(json.load(open(sold_path)))
        for it in items:
            if it["id"] in forced and not it.get("sold"):
                it["sold"] = True
                it.setdefault("sold_at", date.today().isoformat())
    return items


def is_nwt(it):
    return bool(re.search(r"\(NWT\)|new with tags", it.get("name", "") + " " + it.get("description", ""), re.I))


def clean_name(it):
    return re.sub(r"\s*\(NWT\)", "", it.get("name", "")).strip()


def describe(it):
    parts = [it.get("description") or clean_name(it),
             ", ".join(d for d in (f"Size {it['size']}" if it.get("size") else "", it.get("color", "")) if d),
             "Donated and triple inspected. 10% of every sale goes to Love Chapel's food pantry in Columbus, Indiana."]
    return " ".join(p if p.endswith(".") else p + "." for p in parts if p)


def sold_expired(it):
    if not it.get("sold"):
        return False
    when = it.get("sold_at") or it.get("added") or ""
    try:
        return date.fromisoformat(when[:10]) < date.today() - timedelta(days=SOLD_KEEP_DAYS)
    except ValueError:
        return True


def feed_row(it):
    dept = it.get("department", "")
    return {
        "id": it["id"],
        "title": clean_name(it)[:150],
        "description": describe(it)[:9999],
        "availability": "out of stock" if it.get("sold") else "in stock",
        "condition": "new" if is_nwt(it) else "used",
        "price": f"{float(it['price']):.2f} USD" if it.get("price") else "",
        "link": f"{SITE_URL}items/{it['id']}.html",
        "image_link": SITE_URL + it["image"] if it.get("image") else "",
        "additional_image_link": ",".join(SITE_URL + p for p in it.get("more_images", [])),
        "brand": it.get("brand") or BRAND,
        "google_product_category": GOOGLE_CATEGORY.get(it.get("category", ""), CLOTHING),
        "size": it.get("size", ""),
        "color": it.get("color", ""),
        "gender": {"Women's": "female", "Men's": "male"}.get(dept, "unisex"),
        "age_group": "kids" if dept == "Kids" else "adult",
    }


def problems(row, it):
    """Why Meta would reject this row (empty list when it's fine)."""
    out = []
    for col in ("id", "title", "description", "availability", "condition", "price", "link", "image_link", "brand"):
        if not row[col]:
            out.append(f"no {col.replace('_link', '').replace('image', 'photo')}")
    if row["price"] and not re.fullmatch(r"\d+\.\d\d USD", row["price"]):
        out.append(f"bad price {row['price']!r}")
    if it.get("image"):
        path = os.path.join(ROOT, it["image"])
        if not os.path.exists(path):
            out.append("photo file missing")
        else:
            w, h = Image.open(path).size
            if w < 500 or h < 500:
                out.append(f"photo too small ({w}x{h}, needs 500x500)")
    return out


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title} · Amy's Closet</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="product">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
{og_image}
<meta property="product:brand" content="{brand}">
<meta property="product:availability" content="{availability}">
<meta property="product:condition" content="{condition}">
{og_price}
<meta property="product:retailer_item_id" content="{id}">
<script type="application/ld+json">{jsonld}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Figtree:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap">
<style>
:root {{
  --paper: #f4f5f7; --card: #ffffff; --ink: #1d2740; --ink-soft: #4b5672; --line: #d9dde6;
  --tag: #efe3c4; --tag-ink: #4a3b14; --thread: #c9881c; --thread-ink: #ffffff;
  --display: "Young Serif", Georgia, serif; --body: "Figtree", system-ui, sans-serif; --mono: "DM Mono", ui-monospace, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --paper: #121725; --card: #1a2133; --ink: #e8ecf5; --ink-soft: #a7b0c6; --line: #2c3550;
    --tag: #3a321d; --tag-ink: #f1e3bd; --thread: #e2a73f; --thread-ink: #1a1405; color-scheme: dark; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 400 1.0625rem/1.6 var(--body); padding-inline: 16px; }}
.wrap {{ max-width: 1000px; margin-inline: auto; padding-block: 20px 64px; }}
.top {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; padding-bottom: 20px; }}
.brand {{ font-family: var(--display); font-size: 1.4rem; text-decoration: none; color: inherit; }}
.back {{ color: var(--ink-soft); font-weight: 500; }}
.item {{ display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 36px; align-items: start; }}
.photo {{ background: var(--line); border-radius: 14px; overflow: hidden; }}
.photo img {{ display: block; width: 100%; height: auto; }}
.ph {{ aspect-ratio: 4 / 5; display: grid; place-items: center; color: var(--ink-soft); font: 500 0.9rem var(--mono); }}
.info {{ display: grid; gap: 14px; min-width: 0; }}
h1 {{ font: 400 clamp(1.8rem, 4vw, 2.6rem)/1.15 var(--display); margin: 0; text-wrap: balance; }}
.price {{ font: 400 2rem/1 var(--display); font-variant-numeric: tabular-nums; }}
.facts {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.fact {{ font: 500 0.82rem/1 var(--mono); letter-spacing: 0.06em; text-transform: uppercase; padding: 8px 10px; border-radius: 6px; background: var(--card); border: 1px solid var(--line); color: var(--ink-soft); }}
.badge {{ background: var(--tag); color: var(--tag-ink); border-color: transparent; }}
.sold {{ background: var(--ink); color: var(--paper); border-color: transparent; }}
.desc {{ color: var(--ink-soft); }}
.btn {{ display: inline-flex; justify-content: center; padding: 15px 24px; border-radius: 999px; font: 600 1.05rem/1 var(--body); text-decoration: none; background: var(--ink); color: var(--paper); }}
.btn.alt {{ background: transparent; color: var(--ink); border: 2px solid var(--ink); }}
.ctas {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.note {{ font-size: 0.95rem; color: var(--ink-soft); border-top: 1px solid var(--line); padding-top: 14px; }}
a:focus-visible {{ outline: 3px solid var(--thread); outline-offset: 3px; }}
@media (max-width: 760px) {{ .item {{ grid-template-columns: minmax(0, 1fr); gap: 20px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <a class="brand" href="../index.html">Amy's Closet</a>
    <a class="back" href="../index.html#shop">← Back to the rack</a>
  </header>
  <main class="item">
    <div class="photo">{photo}</div>
    <div class="info">
      <div class="facts">{facts}</div>
      <h1>{title}</h1>
      <span class="price">{price_text}</span>
      <p class="desc">{desc_short}</p>
      <div class="ctas">{ctas}</div>
      <p class="note">Every piece is donated and inspected three times before it's listed. All sales final.
        10% of every sale goes to Love Chapel's food pantry in Columbus, Indiana.</p>
    </div>
  </main>
</div>
</body>
</html>
"""


def item_page(it):
    e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731
    url = f"{SITE_URL}items/{it['id']}.html"
    title = clean_name(it)
    desc = describe(it)
    sold = bool(it.get("sold"))
    price = f"{float(it['price']):.2f}" if it.get("price") else ""
    facts = []
    if sold:
        facts.append('<span class="fact sold">Sold</span>')
    if is_nwt(it):
        facts.append('<span class="fact badge">New with tags</span>')
    for v in (f"Size {it['size']}" if it.get("size") else "", it.get("color"), it.get("category")):
        if v:
            facts.append(f'<span class="fact">{e(v)}</span>')
    if sold:
        ctas = f'<a class="btn alt" href="../index.html#shop">See what\'s still on the rack</a>'
    elif it.get("depop"):
        ctas = (f'<a class="btn" href="{e(it["depop"])}" rel="noopener">Buy on Depop</a>'
                f'<a class="btn alt" href="{FACEBOOK}" rel="noopener">Ask a question</a>')
    else:
        ctas = f'<a class="btn" href="{FACEBOOK}" rel="noopener">Message us to buy</a>'
    jsonld = {
        "@context": "https://schema.org", "@type": "Product", "name": title, "description": desc,
        "sku": it["id"], "brand": {"@type": "Brand", "name": it.get("brand") or BRAND},
        "itemCondition": "https://schema.org/NewCondition" if is_nwt(it) else "https://schema.org/UsedCondition",
    }
    if it.get("image"):
        jsonld["image"] = SITE_URL + it["image"]
    if price:
        jsonld["offers"] = {"@type": "Offer", "price": price, "priceCurrency": "USD", "url": url,
                            "availability": "https://schema.org/" + ("SoldOut" if sold else "InStock")}
    return PAGE.format(
        title=e(title), desc=e(desc), url=e(url), id=e(it["id"]), brand=e(it.get("brand") or BRAND),
        availability="out of stock" if sold else "in stock", condition="new" if is_nwt(it) else "used",
        og_image=f'<meta property="og:image" content="{e(SITE_URL + it["image"])}">' if it.get("image") else "",
        og_price=(f'<meta property="product:price:amount" content="{price}">\n'
                  f'<meta property="product:price:currency" content="USD">') if price else "",
        jsonld=json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/"),
        photo=(f'<img src="../{e(it["image"])}" alt="{e(title)}">' if it.get("image")
               else '<div class="ph">Photo coming soon</div>'),
        facts="".join(facts), price_text=f"${price}" if price else "Ask us for the price",
        desc_short=e(it.get("description") or ""), ctas=ctas,
    )


CHECKOUT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Checkout · Amy's Closet</title>
<style>body{margin:0;padding:40px 16px;font:400 1.05rem/1.6 system-ui,sans-serif;background:#f4f5f7;color:#1d2740}
@media (prefers-color-scheme: dark){body{background:#121725;color:#e8ecf5}} a{color:inherit;font-weight:600}</style>
</head><body>
<p id="msg">Taking you to your item…</p>
<script>
  // Meta sends shoppers here as checkout.html?products=<id>:<qty>,<id>:<qty>
  var raw = new URLSearchParams(location.search).get("products") || "";
  var ids = raw.split(",").map(function (p) { return decodeURIComponent(p.split(":")[0]); }).filter(Boolean);
  if (ids.length === 1) location.replace("items/" + encodeURIComponent(ids[0]) + ".html");
  else if (ids.length > 1) {
    document.getElementById("msg").innerHTML = "Your picks:";
    ids.forEach(function (id) { var a = document.createElement("a"); a.href = "items/" + encodeURIComponent(id) + ".html";
      a.textContent = id; var p = document.createElement("p"); p.appendChild(a); document.body.appendChild(p); });
  } else location.replace("index.html#shop");
</script>
</body></html>
"""


def main():
    items = load_items()
    os.makedirs(os.path.join(ROOT, "items"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "feeds"), exist_ok=True)

    for it in items:
        with open(os.path.join(ROOT, "items", f"{it['id']}.html"), "w") as f:
            f.write(item_page(it))
    with open(os.path.join(ROOT, "checkout.html"), "w") as f:
        f.write(CHECKOUT)

    rows, skipped = [], {}
    for it in items:
        if sold_expired(it):
            continue
        row = feed_row(it)
        why = problems(row, it)
        if why:
            skipped[it["id"]] = why
        else:
            rows.append(row)
    with open(os.path.join(ROOT, "feeds", "meta-catalog.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FEED_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    reasons = {}
    for why in skipped.values():
        for r in why:
            reasons[r] = reasons.get(r, 0) + 1
    print(f"{len(items)} item pages. Feed: {len(rows)} rows "
          f"({sum(r['availability'] == 'out of stock' for r in rows)} sold/out of stock), {len(skipped)} left out.")
    for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  left out, {r}: {n}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Meta catalog feed\n{len(rows)} items in the feed, {len(skipped)} left out.\n\n")
            for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
                f.write(f"- left out, {r}: {n}\n")


if __name__ == "__main__":
    sys.exit(main())
