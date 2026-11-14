#!/usr/bin/env python3
"""Adds recordings to media.asitis.cc (bucket prabhupada-media) from a list (Add audio to Cloudflare).

    CF_TOKEN=... CF_ACCOUNT=... add_audio.py <list.json>

The list: [{"key": "audio/1971/710319S2-BOMBAY.mp3", "url": "https://s3.amazonaws.com/vanipedia/...", ...}].
Only adds (owner's request, 14 Nov 2026: the recordings that were missing, mainly from Vanisource):
- a key already in the bucket is left as it is, never overwritten;
- only from Vanisource's and Vedabase's own addresses, only to audio/<year>/<name>.mp3;
- each file is checked to be an MP3 before it is copied, and read back (its size and MD5) after.
Never prints the token. Exit 1 when anything failed.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_r2 import Cloudflare  # noqa: E402

BUCKET = "prabhupada-media"
SOURCES = ("https://s3.amazonaws.com/vanipedia/", "https://vedabase.io/media/", "https://vedabase.cc/media/")
KEY = re.compile(r"^audio/19[67]\d/[A-Za-z0-9 ._()\[\]-]+\.mp3$", re.I)
MAX = 300 * 1024 * 1024


def is_mp3(head):
    return head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; asitis-media)"})
    md5, size = hashlib.md5(), 0
    with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as out:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            size += len(b)
            if size > MAX:
                raise RuntimeError("larger than 300 MB")
            md5.update(b)
            out.write(b)
    return size, md5.hexdigest()


def main(argv):
    token, account = os.environ.get("CF_TOKEN", ""), os.environ.get("CF_ACCOUNT", "")
    if not token or not account:
        print("::error::CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is not set")
        return 1
    items = json.load(open(argv[0], encoding="utf-8"))
    cf = Cloudflare(token, account)
    have = cf.list(BUCKET, prefix="audio/")
    failed, rows = 0, []
    for it in items:
        key, url = it.get("key", ""), it.get("url", "")
        if not KEY.match(key) or not url.startswith(SOURCES) or ".." in key:
            print(f"::error::refused: {key} from {url}")
            failed += 1
            rows.append((key, "refused", ""))
            continue
        if key in have:
            print(f"  there already (left as it is): {key}")
            rows.append((key, "there already", have[key][1]))
            continue
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f.mp3")
            try:
                size, md5 = fetch(url, path)
                with open(path, "rb") as fh:
                    if not is_mp3(fh.read(4)):
                        raise RuntimeError("not an MP3")
                with open(path, "rb") as fh:
                    cf.put(BUCKET, key, fh.read(), "audio/mpeg")
                back = cf.list(BUCKET, prefix=key).get(key)
                if not back or back[1] != size or (back[0] and back[0] != md5):
                    raise RuntimeError(f"read back {back}, sent {size} bytes md5 {md5}")
                print(f"  added: {key} ({size} bytes, read back the same)")
                rows.append((key, "added", size))
            except Exception as e:  # noqa: BLE001
                print(f"::error::{key}: {e}")
                failed += 1
                rows.append((key, f"failed: {e}", ""))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as s:
            s.write("| File on media.asitis.cc | Result | Bytes |\n|---|---|---|\n")
            for k, r, b in rows:
                s.write(f"| `{k}` | {r} | {b} |\n")
    print("All added." if not failed else f"{failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
