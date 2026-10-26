"""Pull new photo posts from the Amy's Closet Facebook Page into products.json.

Runs daily in GitHub Actions (.github/workflows/fb-sync.yml), where Facebook is reachable.
Uses the official Graph API, so it needs a Page access token, not a login or a scraper.

Env:
  FB_PAGE_ID         numeric Page ID (default: Amy's Closet)
  FB_PAGE_TOKEN      long-lived Page access token (repo secret)
  ANTHROPIC_API_KEY  optional; when set, Claude looks at each photo and fills in
                     name, type, department, color, size and price from the tag
  SYNC_DAYS          how far back to look (default 45)
  FIXTURE            path to a saved Graph response, for offline testing
  FIXTURE_IMAGES     folder of <photo_id>.jpg files to use with FIXTURE
"""
import base64
import difflib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(ROOT, "products.json")
IMG_DIR = os.path.join(ROOT, "images", "products")
GRAPH = "https://graph.facebook.com/v23.0"
PAGE_ID = os.environ.get("FB_PAGE_ID", "100091049706849")
RAW_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
# Meta access tokens start with "EAA" and are letters and digits only. Pull one out of whatever was pasted
# (a whole JSON response, "access_token=...", a label, quotes, or line breaks from copying); otherwise use it trimmed.
_found = re.search(r"EAA[A-Za-z0-9]{20,}", re.sub(r"\s+", "", RAW_TOKEN))
TOKEN = _found.group(0) if _found else RAW_TOKEN.strip().strip('"').strip("'").strip()


def describe_token():
    """Say what's wrong with the saved secret without printing it."""
    t = RAW_TOKEN.strip()
    if not t:
        return "The FB_PAGE_TOKEN secret is empty."
    if TOKEN.startswith("EAA"):
        return (f"The FB_PAGE_TOKEN secret holds a {len(TOKEN)}-character token that starts with EAA, but Facebook "
                "rejected it. It was probably cut off when copied, or it has expired.")
    hints = []
    if re.search(r"\s", t):
        hints.append("it contains spaces or line breaks")
    if t.startswith("{"):
        hints.append("it looks like a JSON response with no access_token in it")
    if not hints:
        hints.append("it isn't an access token (those start with EAA)")
    return f"The FB_PAGE_TOKEN secret is {len(t)} characters and " + " and ".join(hints) + "."


def fail(msg):
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Facebook sync stopped\n{msg}\n")
    sys.exit(msg)
DAYS = int(os.environ.get("SYNC_DAYS", "45"))

CATEGORIES = ["Tops", "Bottoms", "Dresses & Jumpsuits", "Outerwear", "Sleepwear", "Scrubs",
              "Swim", "Shoes", "Accessories"]
DEPARTMENTS = ["Women's", "Kids", "Men's", "Shoes & Accessories", "Mixed"]


def graph_get(path, **params):
    params["access_token"] = TOKEN
    url = path if path.startswith("http") else f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # Show Facebook's own explanation (bad token, wrong Page ID, missing permission...).
        body = e.read().decode("utf-8", "replace")
        where = "next page" if path.startswith("http") else path
        msg = f"Facebook API error {e.code} on {where}: {body}"
        if '"code":190' in body.replace(" ", ""):
            msg += ("\n" + describe_token() + " Make a new Page access token (SETUP.md section 3C, step 4), copy "
                    "only the long value that starts with EAA, and paste it as the FB_PAGE_TOKEN repository secret.")
        fail(msg)


def graph_try(path, **params):
    """Like graph_get, but returns (data, error_dict) instead of stopping the run."""
    params["access_token"] = TOKEN
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.loads(e.read().decode("utf-8", "replace")).get("error", {})
        except ValueError:
            return None, {"code": e.code, "message": str(e)}


SOLD_RE = re.compile(r"\bsold\b", re.I)


def photo_says_sold(data):
    texts = [data.get("name") or ""] + [c.get("message") or "" for c in data.get("comments", {}).get("data", [])]
    return any(SOLD_RE.search(t) for t in texts)


def check_sold(items):
    """Mark items sold when Amy marks them on Facebook.

    An item counts as sold when its Facebook photo's caption or a comment on it says "SOLD",
    or when the photo has been deleted from the Page.
    """
    if os.environ.get("FIXTURE"):
        return 0
    open_items = [it for it in items if it.get("fb_photo_id") and not it.get("sold")]
    marked = 0
    fields = "name,comments.limit(50){message}"
    for i in range(0, len(open_items), 50):
        chunk = open_items[i:i + 50]
        data, err = graph_try("", ids=",".join(it["fb_photo_id"] for it in chunk), fields=fields)
        if err:  # one deleted photo fails the whole batch; check each one on its own
            data = {}
            for it in chunk:
                one, e1 = graph_try(it["fb_photo_id"], fields=fields)
                if one:
                    data[it["fb_photo_id"]] = one
                elif e1.get("code") == 100:  # "does not exist": the photo was deleted
                    data[it["fb_photo_id"]] = {"deleted": True}
                else:
                    print(f"  couldn't check {it['id']}: {e1.get('message')}")
        for it in chunk:
            d = data.get(it["fb_photo_id"])
            if d and (d.get("deleted") or photo_says_sold(d)):
                it["sold"] = True
                it["sold_at"] = datetime.now(timezone.utc).date().isoformat()
                marked += 1
                print(f"  marked sold: {it['name']} ({'photo deleted' if d.get('deleted') else 'says SOLD'})")
    return marked


def fetch_posts():
    """Yield (post, [photo_id, ...]) for posts in the window, newest first."""
    if os.environ.get("FIXTURE"):
        for post in json.load(open(os.environ["FIXTURE"]))["data"]:
            yield post, photo_ids(post)
        return
    since = int((datetime.now(timezone.utc) - timedelta(days=DAYS)).timestamp())
    fields = "id,message,created_time,permalink_url,attachments{media_type,target,subattachments.limit(50){media_type,target}}"
    page = graph_get(f"{PAGE_ID}/posts", fields=fields, since=since, limit=50)
    while True:
        for post in page.get("data", []):
            yield post, photo_ids(post)
        nxt = page.get("paging", {}).get("next")
        if not nxt:
            break
        page = graph_get(nxt)


def photo_ids(post):
    ids = []
    for att in post.get("attachments", {}).get("data", []):
        subs = att.get("subattachments", {}).get("data", [])
        for a in subs or [att]:
            if a.get("media_type") == "photo" and a.get("target", {}).get("id"):
                ids.append(a["target"]["id"])
    return ids


def download_photo(photo_id):
    if os.environ.get("FIXTURE"):
        path = os.path.join(os.environ.get("FIXTURE_IMAGES", ""), f"{photo_id}.jpg")
        return open(path, "rb").read() if os.path.exists(path) else None
    info = graph_get(photo_id, fields="images")
    best = max(info.get("images", []), key=lambda i: i["width"] * i["height"], default=None)
    if not best:
        return None
    with urllib.request.urlopen(best["source"], timeout=60) as r:
        return r.read()


def save_photo(raw, item_id):
    # Same light touch-up as the hand-added photos: brighter, a bit more contrast, sharper.
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    im.thumbnail((1600, 1600))
    im = ImageOps.autocontrast(im, cutoff=0.5)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    im = ImageEnhance.Color(im).enhance(1.08)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    rel = f"images/products/{item_id}.jpg"
    os.makedirs(IMG_DIR, exist_ok=True)
    im.save(os.path.join(ROOT, rel), quality=88, optimize=True, progressive=True)
    buf = io.BytesIO()
    small = im.copy()
    small.thumbnail((1024, 1024))
    small.save(buf, "JPEG", quality=85)
    return rel, buf.getvalue()


def guess_from_caption(caption):
    """What the caption alone tells us: size words and kids/men's/shoes hints."""
    c = (caption or "").lower()
    size = ""
    for word, s in (("extra large", "XL"), ("x-large", "XL"), ("large", "L"), ("medium", "M"), ("small", "S")):
        if word in c:
            size = s
            break
    m = re.search(r"\bsize (\d{1,2}(?:\.5)?)\b", c)
    if m:
        size = m.group(1)
    dept = "Mixed"
    if re.search(r"child|kid|toddler|baby|infant", c):
        dept = "Kids"
    elif re.search(r"\bmen'?s\b", c):
        dept = "Men's"
    elif re.search(r"shoe|boot|sandal|sneaker|purse|bag|jewel", c):
        dept = "Shoes & Accessories"
    return size, dept


LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Short shopper-friendly name, e.g. 'Red embroidered tree cardigan'"},
        "category": {"type": "string", "enum": CATEGORIES},
        "department": {"type": "string", "enum": DEPARTMENTS},
        "color": {"type": "string", "description": "Main color(s), e.g. 'Navy/cream'"},
        "description": {"type": "string", "description": "One short line on style and details"},
        "size": {"type": "string", "description": "Size from the tag or caption, or empty if not visible"},
        "price": {"type": "string", "description": "Price from the hang tag like '5.99', or empty if not readable"},
    },
    "required": ["name", "category", "department", "color", "description", "size", "price"],
    "additionalProperties": False,
}


def label_with_claude(client, jpeg, caption):
    response = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"format": {"type": "json_schema", "schema": LABEL_SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.standard_b64encode(jpeg).decode()}},
                {"type": "text", "text": (
                    "This photo is one item for sale at Amy's Closet, a donated-clothing thrift shop. "
                    "Describe the item on the hanger or stand in the middle of the photo, not the racks behind it. "
                    "Read the size and price from its paper hang tag only if you can actually read them; "
                    "otherwise leave them empty. Use 'Mixed' for department when you can't tell.\n\n"
                    f"The Facebook caption for this post was: {caption or '(none)'}"
                )},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text) if text else None


def find_match(items, label, posted):
    """An existing photo-less item from the same day with a similar name (e.g. from the first scrape)."""
    best, best_score = None, 0.0
    for it in items:
        if it.get("image") or it.get("added") != posted:
            continue
        score = difflib.SequenceMatcher(None, it["name"].lower(), label["name"].lower()).ratio()
        if (it.get("color") or "").split("/")[0].lower() in label.get("color", "").lower():
            score += 0.15
        if score > best_score:
            best, best_score = it, score
    return best if best_score >= 0.62 else None


def main():
    if not TOKEN and not os.environ.get("FIXTURE"):
        sys.exit("FB_PAGE_TOKEN is not set. Add it as a repository secret (see SETUP.md).")
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()

    items = json.load(open(PRODUCTS))
    known = {it.get("fb_photo_id") for it in items if it.get("fb_photo_id")}
    added = attached = 0

    for post, ids in fetch_posts():
        caption = post.get("message", "")
        posted = post.get("created_time", "")[:10]
        size_hint, dept_hint = guess_from_caption(caption)
        for pid in ids:
            if pid in known:
                continue
            raw = download_photo(pid)
            if not raw:
                print(f"  couldn't download photo {pid}; will retry next run")
                continue
            item_id = f"fbp-{pid}"
            rel, jpeg = save_photo(raw, item_id)
            label = None
            if client:
                try:
                    label = label_with_claude(client, jpeg, caption)
                except Exception as e:  # keep syncing; the item still lands with basic info
                    print(f"  labeling failed for {pid}: {e}")
            label = label or {"name": "New arrival", "category": "", "department": dept_hint, "color": "",
                              "description": caption.split("\n")[0][:120], "size": "", "price": ""}

            match = find_match(items, label, posted) if label["name"] != "New arrival" else None
            if match:
                match.update({"image": rel, "fb_photo_id": pid, "fb_post": post.get("permalink_url", "")})
                for k in ("size", "price"):
                    if not match.get(k) and label.get(k):
                        match[k] = label[k]
                attached += 1
                print(f"  photo attached to existing item: {match['name']}")
            else:
                items.append({
                    "id": item_id, "name": label["name"], "size": label["size"] or size_hint,
                    "price": label["price"], "image": rel, "depop": "", "added": posted, "sold": False,
                    "category": label["category"], "department": label["department"] or dept_hint,
                    "color": label["color"], "description": label["description"], "source": "facebook-sync",
                    "fb_photo_id": pid, "fb_post": post.get("permalink_url", ""),
                    "needs_review": label["name"] == "New arrival",
                })
                added += 1
                print(f"  added: {label['name']} ({posted})")
            known.add(pid)

    sold = check_sold(items)

    items.sort(key=lambda p: p.get("added", ""))
    with open(PRODUCTS, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Done: {added} new items, {attached} photos attached to existing items, {sold} marked sold.")


if __name__ == "__main__":
    main()
