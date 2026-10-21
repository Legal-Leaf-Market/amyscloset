"""One-time import of Amy's Closet Facebook photos collected by hand in the browser.

Inputs (committed to the repo):
  data/fb-import/part-*.json  one record per Facebook photo: pos, fbid, t (unix time), cap, src (CDN url)
  data/fb-import/labels.json  pos -> "action|data" written after looking at each photo:
      map|<item id>[|key=value;...]   attach this photo to an existing item (optional field fixes)
      keep|<item id>                  item already has a photo; just remember the Facebook photo id
      new|name;category;department;color;size[|price]
      skip|<reason>                   not an item (store shot, portrait)

Runs in GitHub Actions (.github/workflows/fb-manual-import.yml), where Facebook's CDN is reachable.
Photos get the same touch-up as the daily sync. Items carry fb_photo_id so the sync never duplicates them.
"""
import glob
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fb_sync import PRODUCTS, ROOT, save_photo  # noqa: E402

DATA = os.path.join(ROOT, "data", "fb-import")
TZ = ZoneInfo("America/Indiana/Indianapolis")


def download(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (amyscloset import)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # retry, then give up on this photo
            print(f"  download failed (try {attempt + 1}): {e}")
            time.sleep(2)
    return None


def main():
    labels = json.load(open(os.path.join(DATA, "labels.json")))
    records = []
    for path in sorted(glob.glob(os.path.join(DATA, "part-*.json"))):
        records += json.load(open(path))
    records.sort(key=lambda r: r["pos"])
    print(f"{len(records)} photo records, {len(labels)} labels")

    items = json.load(open(PRODUCTS))
    by_id = {it["id"]: it for it in items}
    known = {it.get("fb_photo_id") for it in items if it.get("fb_photo_id")}
    stats = {"attached": 0, "added": 0, "kept": 0, "skipped": 0, "already": 0, "failed": []}

    for rec in records:
        label = labels.get(str(rec["pos"]))
        if not label:
            print(f"  no label for photo #{rec['pos']}; skipping")
            stats["skipped"] += 1
            continue
        action, _, rest = label.partition("|")
        fbid = rec["fbid"]
        posted = datetime.fromtimestamp(rec["t"], TZ).strftime("%Y-%m-%d")
        post_url = f"https://www.facebook.com/photo/?fbid={fbid}"

        if action == "skip":
            stats["skipped"] += 1
            continue
        if action == "keep":
            it = by_id.get(rest)
            if it:
                it["fb_photo_id"] = fbid
                it.setdefault("fb_post", post_url)
                stats["kept"] += 1
            continue
        if fbid in known:
            stats["already"] += 1
            continue

        raw = download(rec["src"])
        if not raw:
            stats["failed"].append(rec["pos"])
            continue

        if action == "map":
            item_id, _, fixes = rest.partition("|")
            it = by_id.get(item_id)
            if not it:
                print(f"  photo #{rec['pos']}: item {item_id} not found")
                stats["failed"].append(rec["pos"])
                continue
            rel, _ = save_photo(raw, it["id"])
            it.update({"image": rel, "fb_photo_id": fbid, "fb_post": post_url})
            for pair in filter(None, fixes.split(";")):
                k, _, v = pair.partition("=")
                it[k] = v
            stats["attached"] += 1
        elif action == "new":
            fields, _, price = rest.partition("|")
            name, category, department, color, size = (fields.split(";") + [""] * 5)[:5]
            item_id = f"fbp-{fbid}"
            rel, _ = save_photo(raw, item_id)
            item = {
                "id": item_id, "name": name, "size": size, "price": price, "image": rel, "depop": "",
                "added": posted, "sold": False, "category": category, "department": department,
                "color": color, "description": rec.get("cap", ""), "source": "facebook",
                "fb_photo_id": fbid, "fb_post": post_url,
            }
            items.append(item)
            by_id[item_id] = item
            stats["added"] += 1
        known.add(fbid)

    items.sort(key=lambda p: p.get("added", ""))
    with open(PRODUCTS, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Done: {stats['attached']} photos attached to existing items, {stats['added']} new items, "
          f"{stats['kept']} kept, {stats['skipped']} skipped, {stats['already']} already imported.")
    if stats["failed"]:
        print(f"Couldn't download photos #{stats['failed']}; their links may have expired.")


if __name__ == "__main__":
    main()
