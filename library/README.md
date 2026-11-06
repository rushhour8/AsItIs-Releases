# library/

Śrīla Prabhupāda's original books (and the app's dictionary), as the **library APK** of As It Is
downloads them on its first start (`AsItIs-v1.0-library-release.apk`, under 60 MB).

- Each file is one book's database, compressed and then encrypted (AES-256-GCM). It is not a
  readable file outside the app, and nothing here needs to be opened or edited by hand.
- The app checks every file against the list built into it (size and SHA-256), downloads it into its
  own private storage, and installs it encrypted for that phone. A file that does not match is never
  kept.
- `library.json` lists the files of the latest build. A file is never changed once published: its
  name carries the start of its own SHA-256, so a changed book is a new file, and older apps keep
  finding the files they list.
- Do not rename, edit or delete these files: an installed app that lists a missing file cannot
  finish its download.

The files are made by the AsItIs build (GitHub Actions, "Build and check the library APK and its
library") and published here from its `AsItIs-library` artifact.
