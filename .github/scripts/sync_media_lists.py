#!/usr/bin/env python3
"""Copies the media lists edited here to the media bucket (prabhupada-media), owner's request
(25 Nov 2026: an edit on GitHub reaches Cloudflare by itself):

    media/audio/recordings-extra.tsv  ->  audio/recordings-extra.tsv   (talks' recordings)
    media/letters/scans-extra.tsv     ->  letters/scans-extra.tsv      (letters' originals)
    media/music/songs.json            ->  music/songs.json             (the Music list)

Only these three files, each checked first (the TSVs: text; songs.json: valid JSON with a song
list, every file under music/); a file copied only when R2 has not the same bytes, then read back.
Nothing in the bucket is ever removed. Never prints the token. Exit 1 when anything failed.

    CF_TOKEN=... CF_ACCOUNT=... sync_media_lists.py
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_r2 import Cloudflare  # noqa: E402

BUCKET = "prabhupada-media"
FILES = {
    "media/audio/recordings-extra.tsv": ("audio/recordings-extra.tsv", "text/tab-separated-values; charset=utf-8"),
    "media/letters/scans-extra.tsv": ("letters/scans-extra.tsv", "text/tab-separated-values; charset=utf-8"),
    "media/music/songs.json": ("music/songs.json", "application/json"),
}
SONG_FILE = re.compile(r"^music/[A-Za-z0-9 ._()\[\]-]+\.(?:mp3|m4a)$", re.I)
MAX = 2 * 1024 * 1024


def check(local, data):
    if len(data) > MAX:
        raise ValueError("larger than 2 MB")
    text = data.decode("utf-8")
    if local.endswith(".json"):
        songs = json.loads(text).get("songs")
        if not isinstance(songs, list) or not songs:
            raise ValueError("no song list in it")
        for s in songs:
            if not s.get("id") or not s.get("title") or not SONG_FILE.match(s.get("file", "")):
                raise ValueError(f"a song not well made: {s!r}"[:200])


def main():
    token, account = os.environ.get("CF_TOKEN", ""), os.environ.get("CF_ACCOUNT", "")
    if not token or not account:
        print("::warning::CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is not set: nothing copied")
        return 0
    cf = Cloudflare(token, account)
    failed = 0
    for local, (key, ctype) in FILES.items():
        if not os.path.isfile(local):
            continue
        data = open(local, "rb").read()
        try:
            check(local, data)
            have = cf.list(BUCKET, prefix=key).get(key)
            if have and have[1] == len(data) and have[0] == hashlib.md5(data).hexdigest():
                print(f"  the same already: {key}")
                continue
            cf.put(BUCKET, key, data, ctype)
            back = cf.get(BUCKET, key)
            if back != data:
                raise RuntimeError("read back different")
            print(f"  copied: {local} -> {BUCKET}/{key} ({len(data)} bytes)")
        except Exception as e:  # noqa: BLE001
            print(f"::error::{local}: {e}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
