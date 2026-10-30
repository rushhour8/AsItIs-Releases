# As It Is: releases and updates

This public repository holds what the As It Is app needs to update itself. The app's source stays private in `rushhour8/AsItIs`.

- **`update.json`**: the published version. The app reads it live each time it starts. It asks GitHub's API for the file as it is now (`https://api.github.com/repos/rushhour8/AsItIs-Releases/contents/update.json?ref=main`), and reads `https://raw.githubusercontent.com/rushhour8/AsItIs-Releases/main/update.json` when the API cannot answer.
- **This repository must be public.** A private repository answers the app (which signs in to nothing) with "not found", for `update.json` and for the APKs alike.
- **Releases**: each version's APK, attached to a release as **`AsItIs.apk`**.

## How the app uses it

1. **When it checks:** at each start, when the phone is online, the app reads `update.json`. Opened offline, it reads it as soon as the phone comes online while the app is in use. Once it has had an answer, it does not check again by itself until the next start. *Check for update* in the side panel reads it whenever asked.
   - **An edit is seen at once:** the app asks GitHub's API, which has no CDN copy, with a fresh `?t=…` each time and `Cache-Control: no-cache, no-store, must-revalidate` and `Pragma: no-cache`. (The raw address alone took 10–15 minutes: its CDN keeps a copy.) The API answers 60 requests an hour from each internet address; past that, the raw address is read.
2. **What it compares:** `latestVersionCode` with the installed app's `versionCode`. If it is higher, the update popup opens with `latestVersionName` and `releaseNotes`.
3. **Download update:** the app downloads `apkUrl` itself, without the browser, showing progress.
   - It does not compare the file with `update.json` (its version, size or SHA-256). Once downloaded, the file goes straight to Android's installer.
   - So the APK at `apkUrl` must be the version `update.json` names: an older APK installs, and the popup comes back.
4. **Install:** the app hands the APK to Android's installer.
   - The first time, Android asks the reader to allow installing apps from As It Is.
   - Android then asks the reader to confirm the install.
   - Android installs the update only if it is signed with the same key as the installed app.
   - Nothing is installed silently.
5. **Later** closes the popup until the next start. With **`"forceUpdate": true`** there is no *Later*, and the popup cannot be closed until the update is installed. Do not set it while testing with an APK older than `latestVersionCode`: the popup would come back after every install, and could not be closed.

Offline, or when `update.json` cannot be read or is invalid, the app shows nothing at start.

## Publishing a version

1. **Build it** (in `rushhour8/AsItIs`):
   - Raise `versionCode` (for example `4` → `5`) and `versionName` (`0.4.0` → `0.5.0`) in `app/build.gradle.kts`.
   - Build the release APK with **your release key**: `./gradlew :app:assembleRelease`. That repository's `claude files/UPDATES_AND_RELEASES.md` says how to give Gradle the key; the key is never committed.
   - Rename `app/build/outputs/apk/release/app-release.apk` to **`AsItIs.apk`**.
2. **Note its size and checksum:**
   - `stat -c %s AsItIs.apk`, or on macOS `stat -f %z AsItIs.apk`;
   - `sha256sum AsItIs.apk`, or on macOS `shasum -a 256 AsItIs.apk`.
3. **Release it here:** *Releases* → *Draft a new release*.
   - Use the tag `v0.5.0` and attach `AsItIs.apk`.
   - Write the notes, then *Publish release*.
   - Do not mark it as a pre-release or leave it as a draft: `releases/latest` links skip those.
4. **Edit `update.json` last**, on `main`, so the app never points at a release that is not there yet:
   - `latestVersionCode` and `latestVersionName`;
   - `apkSha256` and `apkSizeBytes` (from step 2);
   - `releaseNotes` and `publishedAt`;
   - only when needed: `forceUpdate`, `minimumSupportedVersionCode`.

   `apkUrl` can stay `https://github.com/rushhour8/AsItIs-Releases/releases/latest/download/AsItIs.apk`, which always points at the latest release's `AsItIs.apk`.
5. **The check** (*Actions* → *Check update.json*) runs on the change.
   - It fails if the file is not what the app accepts.
   - It also downloads the APK and warns if its size or checksum differ from the file (the app no longer checks them).
   - Fix anything it reports before readers see it.

## The fields

| Field | Change each release? | Meaning |
|---|---|---|
| `schemaVersion` | no (`1`) | Format of this file. |
| `packageName` | no (`cc.asitis.app`) | Must be the app's package name. |
| `latestVersionCode` | **yes** | The new APK's `versionCode`, higher than every earlier one. This is what the app compares. |
| `latestVersionName` | **yes** | The new APK's `versionName`, shown in the popup. |
| `minimumSupportedVersionCode` | when needed | Installed versions below it must update, as with `forceUpdate`. |
| `forceUpdate` | when needed | `true`: the update must be installed. No *Later*, and the popup cannot be closed. |
| `releaseUrl` | optional | The release page (https). |
| `apkUrl` | if the file name changes | The APK's download link (https). |
| `apkSha256` | recommended | The APK's SHA-256, 64 hex characters, or `""`. Shown for checking by hand; the check above compares it. The app does not. |
| `apkSizeBytes` | recommended | The APK's size in bytes, or `0`. Shown as the download's size until the server tells it. |
| `releaseNotes` | **yes** | The text shown in the popup. |
| `publishedAt` | optional | The release date, `YYYY-MM-DD`. |

**One switch, `forceUpdate`.** Earlier files had two. `isForceUpdate` was this switch under another name; the app still reads it. `mandatory` only titled the popup "Update Required", and the popup could still be put off. The app no longer reads it, and the check warns about either.

## Signing

Android installs an update only over an app **signed with the same key**. Use one release key for every release and keep it backed up: if the key is lost, readers must uninstall and reinstall, and lose their highlights and places.

Test APKs from development builds are signed with a different, debug key. Uninstall such a build once before installing the first release; the in-app update works from then on.

## Now

- `update.json` names **v1 (code 5)**, with `forceUpdate` false. Its `apkUrl` is the release tagged `asitis`, `AsItIs-0.4.0-preview.apk`. That APK is version 0.4.0 (code 4), so once installed the app is still code 4 and is offered code 5 again. Attach an APK built as code 5 to test the whole round.
- **This repository is private.** The app is told "not found" until it is public again.
