"""Checks update.json the way the As It Is app reads it, so a broken file never reaches readers
(and share.json and policy.json, which the app reads too).

Fails when the file is not what the app accepts: not JSON, another app's package, a version code
that is not a positive whole number, a link that is not https, a checksum that is not a SHA-256.
Once this repository has a release, the APK link must download. When the file gives a size or a
SHA-256 that the download does not match, it warns: the app no longer checks them (it hands the
download to Android's installer), so a wrong file would reach readers' installers.

Run from the repository's root: python3 .github/scripts/check_update_json.py
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

PACKAGE = "cc.asitis.app"
errors = []
warnings = []


def fail(message):
    errors.append(message)


def https(url):
    return isinstance(url, str) and url.startswith("https://")


with open("update.json", encoding="utf-8") as f:
    text = f.read()
try:
    m = json.loads(text)
except json.JSONDecodeError as e:
    print(f"::error file=update.json,line={e.lineno}::update.json is not valid JSON: {e.msg}")
    sys.exit(1)

if m.get("schemaVersion", 1) != 1:
    fail("schemaVersion must be 1 (the format the app reads)")
if m.get("packageName") != PACKAGE:
    fail(f'packageName must be "{PACKAGE}"')
code = m.get("latestVersionCode")
if not isinstance(code, int) or isinstance(code, bool) or code <= 0:
    fail("latestVersionCode must be a whole number above 0 (the new APK's versionCode)")
name = m.get("latestVersionName")
if not isinstance(name, str) or not name.strip():
    fail('latestVersionName must be the new APK\'s versionName, such as "0.5.0"')
minimum = m.get("minimumSupportedVersionCode", 0)
if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
    fail("minimumSupportedVersionCode must be a whole number (0 or more)")
elif isinstance(code, int) and minimum > code:
    fail("minimumSupportedVersionCode cannot be above latestVersionCode")
if "forceUpdate" in m and not isinstance(m["forceUpdate"], bool):
    fail("forceUpdate must be true or false")
# the two switches of earlier files: one now, forceUpdate
if "isForceUpdate" in m:
    if not isinstance(m["isForceUpdate"], bool):
        fail("isForceUpdate must be true or false")
    warnings.append("isForceUpdate is forceUpdate's old name (the app still reads it): write forceUpdate instead")
if "mandatory" in m:
    warnings.append("mandatory is no longer read by the app: use forceUpdate for an update that must be installed")
if not https(m.get("apkUrl")):
    fail("apkUrl must be an https link to the APK")
if m.get("releaseUrl") not in (None, "") and not https(m.get("releaseUrl")):
    fail("releaseUrl must be an https link")
sha = m.get("apkSha256") or ""
if sha and not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
    fail("apkSha256 must be the APK's SHA-256 (64 hexadecimal characters), or empty")
size = m.get("apkSizeBytes") or 0
if not isinstance(size, int) or isinstance(size, bool) or size < 0:
    fail("apkSizeBytes must be the APK's size in bytes, or 0")
if not isinstance(m.get("releaseNotes", ""), str):
    fail("releaseNotes must be text")

# The APK itself: only once a release exists (before the first one, its link cannot work yet).
repo = os.environ.get("GITHUB_REPOSITORY")
token = os.environ.get("GITHUB_TOKEN")
if not errors and repo:
    # the latest published release (not a draft or a pre-release: "releases/latest" links skip those)
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest", headers={"Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as r:
            latest = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        latest = None
    if latest is None:
        warnings.append("this repository has no published release yet: the APK link is not checked until one is published")
    else:
        try:
            digest = hashlib.sha256()
            got = 0
            with urllib.request.urlopen(m["apkUrl"], timeout=120) as r:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
                    got += len(chunk)
            if size and got != size:
                warnings.append(f"apkSizeBytes is {size}, but the APK at apkUrl is {got} bytes")
            if sha and digest.hexdigest() != sha.lower():
                warnings.append(f"apkSha256 does not match the APK at apkUrl (its SHA-256 is {digest.hexdigest()})")
            print(f"APK at apkUrl: {got} bytes, SHA-256 {digest.hexdigest()}")
        except Exception as e:  # noqa: BLE001 - any failure to download is reported as such
            fail(f"the APK at apkUrl could not be downloaded ({e}); the app would show 'not found'")

# share.json: the text "Share app" shares; policy.json: the privacy policy the About page opens
if os.path.exists("share.json"):
    try:
        share = json.load(open("share.json", encoding="utf-8"))
        text = share.get("text")
        if share.get("schemaVersion", 1) != 1:
            fail("share.json: schemaVersion must be 1")
        if not isinstance(text, str) or not text.strip():
            fail("share.json: text must be the text to share")
        elif len(text.strip()) > 4000:
            fail("share.json: text is longer than the 4,000 characters the app takes")
    except json.JSONDecodeError as e:
        fail(f"share.json is not valid JSON: {e.msg} (line {e.lineno})")
if os.path.exists("policy.json"):
    try:
        policy = json.load(open("policy.json", encoding="utf-8"))
        if not policy.get("sections"):
            fail("policy.json: it has no sections")
    except json.JSONDecodeError as e:
        fail(f"policy.json is not valid JSON: {e.msg} (line {e.lineno})")

for w in warnings:
    print(f"::warning file=update.json::{w}")
for e in errors:
    print(f"::error file=update.json::{e}")
if errors:
    sys.exit(1)
print(f"update.json is valid: version {name} (code {code}).")
