#!/usr/bin/env python3
"""The release's notes: .github/release-notes.md with its {{VERSION}}, {{APK_MB}} and {{LIBRARY_MB}} filled in.

    release_notes.py <template> <version> <apk MB> <library MB>   (the notes on stdout)
"""
import re
import sys


def main(argv):
    template, version, apk_mb, lib_mb = argv
    for name, v in (("version", version), ("apk MB", apk_mb), ("library MB", lib_mb)):
        if not re.fullmatch(r"[0-9A-Za-z.\-]{1,20}", v):
            print(f"{name} is not as it must be: {v!r}", file=sys.stderr)
            return 1
    text = open(template, encoding="utf-8").read()
    text = text.replace("{{VERSION}}", version).replace("{{APK_MB}}", apk_mb).replace("{{LIBRARY_MB}}", lib_mb)
    if "{{" in text:
        print("a {{...}} is left in the notes", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
