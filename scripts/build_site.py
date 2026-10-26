"""Build the per-item pages and the Meta (Facebook/Instagram) catalog feed from products.json.

Runs in the Pages deploy (.github/workflows/pages.yml) right before upload, so every deploy,
including the one the Facebook sync triggers, publishes a fresh feed. Nothing it writes is committed.

Outputs:
  items/<id>.html          one page per item: photo, price, size, buy button, Open Graph + schema.org tags
  feeds/meta-catalog.csv   Meta catalog data feed (Commerce Manager > Catalog > Data sources > scheduled feed)
  checkout.html            target for Meta's "checkout URL"; shows the order, or forwards a single item to its page
  sitemap.xml              home page plus every item page still listed, for Google Search Console
  share.jpg                1200x630 link-preview image (og:image on the home page) from in-stock photos

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

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = os.environ.get("SITE_URL", "https://legal-leaf-market.github.io/amyscloset/").rstrip("/") + "/"
FACEBOOK = "https://www.facebook.com/profile.php?id=100091049706849"
SOLD_KEEP_DAYS = 30
BRAND = "Amy's Closet"
SHOP = json.load(open(os.path.join(ROOT, "shop.json"))) if os.path.exists(os.path.join(ROOT, "shop.json")) else {}
SHIP_RATE = SHOP.get("shipping_flat_rate_usd")

FEED_COLUMNS = ["id", "title", "description", "availability", "condition", "price", "link", "image_link",
                "additional_image_link", "brand", "google_product_category", "size", "color", "gender",
                "age_group"] + (["shipping"] if SHIP_RATE else [])

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
        **({"shipping": f"US::Standard:{float(SHIP_RATE):.2f} USD"} if SHIP_RATE else {}),
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
      <p class="note"><strong>We ship.</strong> {ship_text}</p>
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
        ship_text=(f"Shipping is ${float(SHIP_RATE):.2f}, paid by the buyer." if SHIP_RATE
                   else "Shipping is paid by the buyer. Message us for a quote, or pick it up in the store."),
    )


# Meta sends shoppers to checkout.html?products=<id>:<qty>,<id>:<qty>[&coupon=CODE]. The page shows the
# order from the item data baked in below. One available item goes straight to its item page.
CHECKOUT = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Your order · Amy's Closet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Figtree:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap">
<style>
:root {
  --paper: #f4f5f7; --card: #ffffff; --ink: #1d2740; --ink-soft: #4b5672; --line: #d9dde6;
  --tag: #efe3c4; --tag-ink: #4a3b14; --thread: #c9881c;
  --display: "Young Serif", Georgia, serif; --body: "Figtree", system-ui, sans-serif; --mono: "DM Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --paper: #121725; --card: #1a2133; --ink: #e8ecf5; --ink-soft: #a7b0c6; --line: #2c3550;
    --tag: #3a321d; --tag-ink: #f1e3bd; --thread: #e2a73f; color-scheme: dark; }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 1.0625rem/1.6 var(--body); padding-inline: 16px; }
.wrap { max-width: 640px; margin-inline: auto; padding-block: 20px 64px; display: grid; gap: 20px; }
.top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.brand { font-family: var(--display); font-size: 1.4rem; text-decoration: none; color: inherit; }
.back { color: var(--ink-soft); font-weight: 500; }
h1 { font: 400 clamp(1.8rem, 5vw, 2.4rem)/1.15 var(--display); margin: 0; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; display: grid; gap: 16px; }
.lines { list-style: none; margin: 0; padding: 0; display: grid; gap: 16px; }
.line { display: grid; grid-template-columns: 84px minmax(0, 1fr) auto; gap: 14px; align-items: start; }
.line img, .line .ph { width: 84px; aspect-ratio: 4 / 5; object-fit: cover; border-radius: 8px; background: var(--line); display: block; }
.line .name { font-weight: 600; text-decoration: none; color: inherit; overflow-wrap: anywhere; }
.line .meta { font: 400 0.85rem/1.4 var(--mono); color: var(--ink-soft); }
.line .qty-note { font-size: 0.88rem; color: var(--tag-ink); background: var(--tag); border-radius: 6px; padding: 4px 8px; margin-top: 6px; display: inline-block; }
.line .amt { font: 400 1.2rem/1.2 var(--display); font-variant-numeric: tabular-nums; white-space: nowrap; }
.line .depop { display: inline-block; margin-top: 8px; font-weight: 600; font-size: 0.92rem; }
.sums { display: grid; gap: 6px; border-top: 1px solid var(--line); padding-top: 14px; font-variant-numeric: tabular-nums; }
.sums div { display: flex; justify-content: space-between; gap: 12px; }
.sums .total { font: 400 1.4rem/1.3 var(--display); padding-top: 6px; }
.notice { background: var(--tag); color: var(--tag-ink); border-radius: 10px; padding: 12px 14px; font-size: 0.95rem; }
.notice p { margin: 0; } .notice p + p { margin-top: 6px; }
.btn { display: flex; justify-content: center; text-align: center; padding: 16px 24px; border-radius: 999px; font: 600 1.05rem/1.2 var(--body); text-decoration: none; background: var(--ink); color: var(--paper); border: 0; cursor: pointer; width: 100%; }
.btn.alt { background: transparent; color: var(--ink); border: 2px solid var(--ink); }
.how { font-size: 0.95rem; color: var(--ink-soft); margin: 0; }
.fine { font-size: 0.9rem; color: var(--ink-soft); margin: 0; }
a:focus-visible, button:focus-visible { outline: 3px solid var(--thread); outline-offset: 3px; }
@media (max-width: 420px) { .line { grid-template-columns: 64px minmax(0, 1fr); } .line img, .line .ph { width: 64px; } .line .amt { grid-column: 2; } }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <a class="brand" href="index.html">Amy's Closet</a>
    <a class="back" href="index.html#shop">← Back to the rack</a>
  </header>
  <h1>Your order</h1>
  <div class="notice" id="notices" hidden></div>
  <section class="card" id="cart" hidden>
    <ul class="lines" id="lines"></ul>
    <div class="sums">
      <div><span>Items (<span id="count"></span>)</span><span id="subtotal"></span></div>
      <div><span>Shipping (US)</span><span id="shipping"></span></div>
      <div class="total"><span>Total</span><span id="total"></span></div>
    </div>
    <button class="btn" type="button" id="pay">Message us to buy this order</button>
    <p class="how" id="how">We'll copy your order so you can paste it into the message. We reply with how to pay
      and hold the pieces for you. You can also pick up in the store.</p>
  </section>
  <section class="card" id="empty" hidden>
    <p style="margin:0">Nothing in this order is still available. New pieces go on the rack every week.</p>
    <a class="btn alt" href="index.html#shop">See what's on the rack</a>
  </section>
  <p class="fine">Every piece is one of a kind, donated and inspected three times. All sales final.
    10% of every sale goes to Love Chapel's food pantry in Columbus, Indiana.</p>
</div>
<script>
(function () {
  var ITEMS = __ITEMS__;
  var SHIP = __SHIP__;
  var FACEBOOK = __FACEBOOK__;
  var $ = function (id) { return document.getElementById(id); };
  function money(n) { return "$" + n.toFixed(2); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function dec(s) { try { return decodeURIComponent(s); } catch (e) { return s; } }

  var params = new URLSearchParams(location.search);
  // URLSearchParams decodes once; decode again in case Meta's value arrives double-encoded.
  var raw = dec(params.get("products") || "");
  var coupon = dec(params.get("coupon") || "").trim();
  var asked = [], seen = {};
  raw.split(",").forEach(function (part) {
    part = part.trim(); if (!part) return;
    var at = part.lastIndexOf(":");
    var id = at > 0 ? part.slice(0, at) : part, qty = at > 0 ? parseInt(part.slice(at + 1), 10) : 1;
    if (!(qty >= 1)) qty = 1;
    if (seen[id]) { seen[id].qty += qty; return; }
    asked.push(seen[id] = { id: id, qty: qty });
  });
  if (!asked.length) { location.replace("index.html#shop"); return; }

  var lines = [], notes = [];
  asked.forEach(function (a) {
    var it = ITEMS[a.id];
    if (!it) notes.push("One item in your order isn't in our shop anymore, so we left it out.");
    else if (it.sold) notes.push(it.title + " has already sold, so we left it out. Sorry!");
    else if (it.price == null) notes.push(it.title + " doesn't have a price yet. Message us about it.");
    else lines.push({ id: a.id, it: it, more: a.qty > 1 });
  });

  if (lines.length === 1 && !lines[0].more && !notes.length && !coupon) {
    location.replace("items/" + encodeURIComponent(lines[0].id) + ".html"); return;
  }

  if (coupon) notes.push("Coupon " + coupon + ": we don't take online coupon codes yet, so it isn't in this total.");
  if (notes.length) {
    var box = $("notices");
    notes.forEach(function (n) { box.appendChild(el("p", null, n)); });
    box.hidden = false;
  }
  if (!lines.length) { $("empty").hidden = false; return; }

  var subtotal = 0;
  lines.forEach(function (l) {
    var it = l.it, li = el("li", "line"), href = "items/" + encodeURIComponent(l.id) + ".html";
    var pic = el("a"); pic.href = href; pic.setAttribute("aria-hidden", "true"); pic.tabIndex = -1;
    if (it.image) { var img = el("img"); img.src = it.image; img.alt = ""; img.loading = "lazy"; pic.appendChild(img); }
    else pic.appendChild(el("div", "ph"));
    var info = el("div"), name = el("a", "name", it.title); name.href = href;
    info.appendChild(name);
    info.appendChild(el("div", "meta", [it.size && "Size " + it.size, it.color, "Qty 1"].filter(Boolean).join(" · ")));
    if (l.more) info.appendChild(el("span", "qty-note", "One of a kind, so there's just 1 of these."));
    if (it.depop) { var d = el("a", "depop", "Buy this one on Depop →"); d.href = it.depop; d.rel = "noopener"; info.appendChild(d); }
    li.appendChild(pic); li.appendChild(info); li.appendChild(el("span", "amt", money(it.price)));
    $("lines").appendChild(li);
    subtotal += it.price;
  });
  var ship = SHIP == null ? null : SHIP;
  $("count").textContent = lines.length;
  $("subtotal").textContent = money(subtotal);
  $("shipping").textContent = ship == null ? "Quoted by message" : money(ship);
  $("total").textContent = money(subtotal + (ship || 0)) + (ship == null ? " + shipping" : "");
  $("cart").hidden = false;

  var summary = ["Hi! I'd like to buy this order from Amy's Closet:"]
    .concat(lines.map(function (l) { return "- " + l.it.title + (l.it.size ? " (size " + l.it.size + ")" : "") + ", " + money(l.it.price) + " [" + l.id + "]"; }))
    .concat(["Shipping: " + (ship == null ? "please quote" : money(ship)), "Total: " + $("total").textContent]).join("\n");
  $("pay").addEventListener("click", function () {
    var go = function () { location.href = FACEBOOK; };
    try {
      navigator.clipboard.writeText(summary).then(function () {
        $("pay").textContent = "Order copied. Opening Facebook…"; setTimeout(go, 700);
      }, go);
    } catch (e) { go(); }
  });
})();
</script>
</body>
</html>
"""


def checkout_page(items):
    data = {}
    for it in items:
        data[it["id"]] = {
            "title": clean_name(it), "price": float(it["price"]) if it.get("price") else None,
            "image": it.get("image") or "", "size": it.get("size") or "", "color": it.get("color") or "",
            "depop": it.get("depop") or "", "sold": bool(it.get("sold")),
        }
    js = lambda v: json.dumps(v, ensure_ascii=False).replace("</", "<\\/")  # noqa: E731
    return (CHECKOUT.replace("__ITEMS__", js(data))
            .replace("__SHIP__", js(float(SHIP_RATE)) if SHIP_RATE else "null")
            .replace("__FACEBOOK__", js(FACEBOOK)))


def sitemap(items):
    urls = [(SITE_URL, max((it.get("added", "") for it in items), default=""))]
    for it in items:
        if not sold_expired(it):
            urls.append((f"{SITE_URL}items/{it['id']}.html", it.get("sold_at") or it.get("added", "")))
    rows = "".join(f"  <url><loc>{html.escape(u)}</loc>" + (f"<lastmod>{d[:10]}</lastmod>" if d else "") + "</url>\n"
                   for u, d in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n'


def share_image(items, path):
    """Newest in-stock photos side by side over a navy band with the shop name."""
    W, H, BAND = 1200, 630, 150
    photos = [it["image"] for it in reversed(items)
              if it.get("image") and not it.get("sold") and os.path.exists(os.path.join(ROOT, it["image"]))][:4]
    im = Image.new("RGB", (W, H), "#f4f5f7")
    if photos:
        w = W // len(photos)
        for i, rel in enumerate(photos):
            tile = ImageOps.fit(Image.open(os.path.join(ROOT, rel)).convert("RGB"), (w, H - BAND), centering=(0.5, 0.4))
            im.paste(tile, (i * w, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - BAND, W, H], fill="#1d2740")
    d.rectangle([0, H - BAND, W, H - BAND + 6], fill="#c9881c")
    try:
        big, small = ImageFont.load_default(size=58), ImageFont.load_default(size=28)
    except TypeError:  # Pillow without FreeType sizes
        big = small = ImageFont.load_default()
    d.text((48, H - BAND + 26), "Amy's Closet", font=big, fill="#ffffff")
    d.text((48, H - BAND + 96), "Thrift in Columbus, IN · 10% of every sale feeds Love Chapel's pantry",
           font=small, fill="#d9dde6")
    im.save(path, quality=85, optimize=True, progressive=True)


def main():
    items = load_items()
    os.makedirs(os.path.join(ROOT, "items"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "feeds"), exist_ok=True)

    for it in items:
        with open(os.path.join(ROOT, "items", f"{it['id']}.html"), "w") as f:
            f.write(item_page(it))
    with open(os.path.join(ROOT, "checkout.html"), "w") as f:
        f.write(checkout_page(items))
    with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
        f.write(sitemap(items))
    share_image(items, os.path.join(ROOT, "share.jpg"))

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
