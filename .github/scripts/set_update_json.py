#!/usr/bin/env python3
"""Sets update.json to a published APK, keeping its notes for the owner (the lines starting with #),
its "notes" and its "mandatory" as they are.

    set_update_json.py update.json --code 1 --name 1.0 --primary URL --secondary URL --sha256 HEX --size BYTES

Exit 1 (the file unchanged) when a value is not as it must be or the file would not read as the app
reads it (the # lines left out, then JSON).
"""
import argparse
import json
import re
import sys


def app_view(text):
    """update.json as the app reads it: the lines starting with # left out, then JSON."""
    return json.loads("\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#")))


def set_value(text, key, value):
    pattern = re.compile(r'^(\s*"' + re.escape(key) + r'"\s*:\s*)(".*?"|-?\d+|true|false|null)(\s*,?\s*)$', re.M)
    if len(pattern.findall(text)) != 1:
        raise ValueError(f'"{key}" is not once in the file')
    return pattern.sub(lambda m: m.group(1) + json.dumps(value, ensure_ascii=False) + m.group(3), text)


def main(argv):
    a = argparse.ArgumentParser()
    a.add_argument("file")
    a.add_argument("--code", type=int, required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--primary", required=True)
    a.add_argument("--secondary", required=True)
    a.add_argument("--sha256", required=True)
    a.add_argument("--size", type=int, required=True)
    o = a.parse_args(argv)
    if o.code < 1 or not re.fullmatch(r"[0-9A-Za-z.\-]+", o.name):
        print("::error::versionCode or versionName is not as it must be"); return 1
    if not (o.primary.startswith("https://") and o.secondary.startswith("https://")):
        print("::error::the links must start with https://"); return 1
    if not re.fullmatch(r"[0-9a-f]{64}", o.sha256) or o.size <= 0:
        print("::error::sha256 or size is not as it must be"); return 1
    text = open(o.file, encoding="utf-8").read()
    try:
        for k, v in (("versionCode", o.code), ("versionName", o.name), ("primaryLink", o.primary),
                     ("secondaryLink", o.secondary), ("sha256", o.sha256), ("sizeBytes", o.size)):
            text = set_value(text, k, v)
        d = app_view(text)
    except ValueError as e:
        print(f"::error::update.json: {e}"); return 1
    if (d.get("versionCode"), d.get("versionName"), d.get("sha256"), d.get("sizeBytes")) != (o.code, o.name, o.sha256, o.size):
        print("::error::update.json does not read back as set"); return 1
    open(o.file, "w", encoding="utf-8").write(text)
    print(f"update.json: {o.name} ({o.code}), {o.size} bytes, SHA-256 {o.sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
