# The media lists (edited here, copied to Cloudflare by themselves)

Edit a file here and commit it to `main`: **Sync to Cloudflare** copies it to the media bucket
(prabhupada-media, https://media.asitis.cc/) within a minute or two. Phones read it quietly when the
app starts or comes back to the screen (at most every 10 minutes); no new app is needed.

| File here | On Cloudflare | What it is |
|---|---|---|
| `audio/recordings-extra.tsv` | `audio/recordings-extra.tsv` | talks' recordings added, changed or taken away |
| `letters/scans-extra.tsv` | `letters/scans-extra.tsv` | letters' originals (scans) added, changed or taken away |
| `music/songs.json` | `music/songs.json` | the Music list (name, length, file of each song) |

Upload the MP3s or the scans to the bucket first (Cloudflare dashboard > R2 > prabhupada-media >
Upload, or Actions > Add audio to Cloudflare), then edit the list here. Each file's own notes (the
lines starting with #) say how a line is written. Nothing in the bucket is ever removed by this.
