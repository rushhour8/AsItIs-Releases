#!/usr/bin/env python3
"""Makes Cloudflare R2 the same as this repository (Sync to Cloudflare).

  update.json, share.json, notification.json, policy.json  ->  bucket asitis-app      (app.asitis.cc)
  library/*.sealed, library/library.json                    ->  bucket asitis-library  (library.asitis.cc)
  the published release's APK (--apk FILE ...)              ->  bucket asitis-app, apk/<name>

Everything goes through Cloudflare's API with the token (never the public addresses, which the
owner's firewall rule may be blocking on purpose):
- a file is copied only when R2 has not the same bytes (its MD5, R2's ETag, compared first);
- each copy is read back through the API and compared byte for byte;
- R2's sealed files that library/ no longer has are removed (an earlier key's files: owner's
  decision, 13 Nov 2026), and with --apk, every other object under apk/ (one APK published).
Never prints the token. Exit 1 when anything failed.

  CF_TOKEN=... CF_ACCOUNT=... sync_r2.py [--apk AsItIs-v1.1.apk ...]
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.cloudflare.com/client/v4/accounts/{account}/r2/buckets/{bucket}/objects"
APP, LIBRARY = "asitis-app", "asitis-library"
APP_FILES = ["update.json", "share.json", "notification.json", "policy.json"]
SAFE = re.compile(r"^[A-Za-z0-9._-]+$")
JSON_TYPE = "application/json; charset=utf-8"
BINARY = "application/octet-stream"
APK_TYPE = "application/vnd.android.package-archive"


class Cloudflare:
    def __init__(self, token, account, opener=None):
        self.token, self.account = token, account
        self.open = opener or self._urlopen

    def _urlopen(self, method, url, body=None, headers=None):
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        req.add_header("Authorization", "Bearer " + self.token)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                if e.code < 500 and e.code != 429:
                    return e.code, e.read()
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(2 * (attempt + 1))
        return 0, b""

    def url(self, bucket, key=None, query=None):
        u = API.format(account=self.account, bucket=bucket)
        if key is not None:
            u += "/" + urllib.parse.quote(key, safe="/")
        if query:
            u += "?" + urllib.parse.urlencode(query)
        return u

    def list(self, bucket, prefix=None):
        """Every object of [bucket]: key -> (etag, size)."""
        out, cursor = {}, None
        while True:
            q = {"per_page": 1000}
            if prefix:
                q["prefix"] = prefix
            if cursor:
                q["cursor"] = cursor
            code, body = self.open("GET", self.url(bucket, query=q))
            if code != 200:
                raise RuntimeError(f"listing {bucket}: HTTP {code}")
            d = json.loads(body)
            for o in d.get("result") or []:
                out[o["key"]] = ((o.get("etag") or "").strip('"').lower(), o.get("size"))
            info = d.get("result_info") or {}
            cursor = info.get("cursor")
            if not info.get("is_truncated") or not cursor:
                return out

    def put(self, bucket, key, data, ctype):
        code, body = self.open("PUT", self.url(bucket, key), data, {"Content-Type": ctype})
        if code != 200:
            raise RuntimeError(f"{bucket}/{key}: Cloudflare answered HTTP {code} {body[:300]!r}")

    def get(self, bucket, key):
        code, body = self.open("GET", self.url(bucket, key))
        if code != 200:
            raise RuntimeError(f"reading back {bucket}/{key}: HTTP {code}")
        return body

    def delete(self, bucket, key):
        code, body = self.open("DELETE", self.url(bucket, key))
        if code not in (200, 204, 404):
            raise RuntimeError(f"removing {bucket}/{key}: HTTP {code}")


def md5(data):
    return hashlib.md5(data).hexdigest()


def sync(cf, root=".", apks=(), log=print):
    """Returns the number of failures."""
    failed = 0

    def copy(bucket, key, path, ctype, have):
        nonlocal failed
        data = open(path, "rb").read()
        if not data:
            log(f"::error::{path} is empty: not copied")
            failed += 1
            return
        if have.get(key, ("", None))[0] == md5(data):
            log(f"  same: {bucket}/{key}")
            return
        try:
            cf.put(bucket, key, data, ctype)
            back = cf.get(bucket, key)
            if back != data:
                raise RuntimeError(f"the copy of {key} read back is not the same file")
            log(f"  copied: {bucket}/{key} ({len(data)} bytes, read back the same)")
        except RuntimeError as e:
            log(f"::error::{e}")
            failed += 1

    def remove(bucket, key):
        nonlocal failed
        try:
            cf.delete(bucket, key)
            log(f"  removed: {bucket}/{key}")
        except RuntimeError as e:
            log(f"::error::{e}")
            failed += 1

    # the app's files
    app = cf.list(APP)
    for name in APP_FILES:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            copy(APP, name, p, JSON_TYPE, app)

    # the library: the same as library/ (its sealed files and library.json)
    lib_dir = os.path.join(root, "library")
    wanted = {}
    if os.path.isdir(lib_dir):
        for n in sorted(os.listdir(lib_dir)):
            if n.endswith(".sealed") or n == "library.json":
                if not SAFE.match(n):
                    log(f"::error::library/{n}: unexpected name, not copied")
                    failed += 1
                    continue
                wanted[n] = os.path.join(lib_dir, n)
    if wanted:
        have = cf.list(LIBRARY)
        for n, p in wanted.items():
            copy(LIBRARY, n, p, JSON_TYPE if n.endswith(".json") else BINARY, have)
        # only once every listed file is there: an earlier key's files removed
        if failed == 0:
            for key in sorted(have):
                if key.endswith(".sealed") and key not in wanted:
                    remove(LIBRARY, key)
    else:
        log("library/ has no files: Cloudflare's library left as it is")

    # the published APK: apk/<name>, every other object under apk/ removed
    if apks:
        have = cf.list(APP, prefix="apk/")
        keys = set()
        for p in apks:
            n = os.path.basename(p)
            if not SAFE.match(n) or not n.endswith(".apk"):
                log(f"::error::{n}: not an APK's plain name, not copied")
                failed += 1
                continue
            keys.add("apk/" + n)
            copy(APP, "apk/" + n, p, APK_TYPE, have)
        if failed == 0:
            for key in sorted(have):
                if key not in keys:
                    remove(APP, key)
    return failed


def main(argv):
    token, account = os.environ.get("CF_TOKEN", ""), os.environ.get("CF_ACCOUNT", "")
    if not token or not account:
        print("::warning::CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is not set: nothing copied (Settings > Secrets and variables > Actions).")
        return 0
    apks = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--apk" and args:
            apks.append(args.pop(0))
        else:
            print(f"::error::unknown argument {a}")
            return 2
    try:
        failed = sync(Cloudflare(token, account), apks=apks)
    except RuntimeError as e:
        print(f"::error::{e}")
        return 1
    print("Cloudflare is the same as this repository." if not failed else f"{failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
