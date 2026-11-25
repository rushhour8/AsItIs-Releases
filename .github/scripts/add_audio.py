#!/usr/bin/env python3
"""Adds recordings to media.asitis.cc (bucket prabhupada-media) from a list (Add audio to Cloudflare).

    CF_TOKEN=... CF_ACCOUNT=... add_audio.py <list.json>

The list: [{"key": "audio/1971/710319S2-BOMBAY.mp3", "url": "https://s3.amazonaws.com/vanipedia/...", ...}].
Only adds (owner's request, 14 Nov 2026: the recordings that were missing, mainly from Vanisource):
- a key already in the bucket is left as it is, never overwritten;
- only from Vanisource's and Vedabase's own addresses, only to audio/<year>/<name>.mp3 or (owner's
  request, 25 Nov 2026: Srila Prabhupada's singing, from vedabase.cc/music) music/<name>.mp3;
- each file is checked to be an MP3 before it is copied, and read back (its size and MD5) after;
  with "sha256" in the list, the file must be exactly that one (the one checked for duplicates).
- The music's list itself, {"key": "music/songs.json", "file": "songs.json"} (beside the list), is
  the one file that is replaced when it changes.
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
KEY = re.compile(r"^(?:audio/19[67]\d|music)/[A-Za-z0-9 ._()\[\]-]+\.mp3$", re.I)
LIST_KEY = re.compile(r"^music/songs\.json$")
MAX = 300 * 1024 * 1024


def is_mp3(head):
    return head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; asitis-media)"})
    md5, sha, size = hashlib.md5(), hashlib.sha256(), 0
    with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as out:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            size += len(b)
            if size > MAX:
                raise RuntimeError("larger than 300 MB")
            md5.update(b)
            sha.update(b)
            out.write(b)
    return size, md5.hexdigest(), sha.hexdigest()


def main(argv):
    token, account = os.environ.get("CF_TOKEN", ""), os.environ.get("CF_ACCOUNT", "")
    if not token or not account:
        print("::error::CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is not set")
        return 1
    items = json.load(open(argv[0], encoding="utf-8"))
    cf = Cloudflare(token, account)
    have = {**cf.list(BUCKET, prefix="audio/"), **cf.list(BUCKET, prefix="music/")}
    failed, rows = 0, []
    base = os.path.dirname(os.path.abspath(argv[0]))
    for it in items:
        key, url = it.get("key", ""), it.get("url", "")
        if it.get("file"):
            # the music's list: replaced when it has changed
            path = os.path.realpath(os.path.join(base, it["file"]))
            if not LIST_KEY.match(key) or not path.startswith(base + os.sep) or not os.path.isfile(path):
                print(f"::error::refused: {key} from {it['file']}")
                failed += 1
                rows.append((key, "refused", ""))
                continue
            data = open(path, "rb").read()
            json.loads(data.decode("utf-8"))
            if key in have and have[key][1] == len(data) and have[key][0] == hashlib.md5(data).hexdigest():
                rows.append((key, "the same already", len(data)))
                continue
            cf.put(BUCKET, key, data, "application/json")
            back = cf.list(BUCKET, prefix=key).get(key)
            if not back or back[1] != len(data):
                print(f"::error::{key}: read back {back}")
                failed += 1
                rows.append((key, "failed", ""))
            else:
                print(f"  list written: {key} ({len(data)} bytes)")
                rows.append((key, "written", len(data)))
            continue
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
                size, md5, sha = fetch(url, path)
                with open(path, "rb") as fh:
                    if not is_mp3(fh.read(4)):
                        raise RuntimeError("not an MP3")
                if it.get("sha256") and it["sha256"] != sha:
                    raise RuntimeError("not the file checked (its SHA-256 differs)")
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
