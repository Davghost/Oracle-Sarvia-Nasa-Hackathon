# Downloading the GCOV scenes

Each GCOV file is about 3.8 GB. On a slow home connection it takes ~4 h each, so download in the Codespace.

1. Store the Earthdata token as a Codespaces secret named `EARTHDATA_TOKEN` (never in the repo or shell history).
2. Install `requirements-pipeline.txt`.
3. Run `python pipeline/download_gcov.py`.

The downloader was tested on 15 Nov 2026 with `asf_search` 14.1.0 for the
project's two NISAR GCOV granules (5 and 17 Jan 2026). This does not guarantee
that every ASF product or future API version behaves the same way. The
downloaded HDF5 files belong in `data/`, which is ignored by git.

## Fallback with wget

Copy each scene's download URL from ASF Vertex, then in the Codespace:

```bash
wget --header="Authorization: Bearer $EARTHDATA_TOKEN" -P data/ "<URL_FROM_VERTEX>"
```

(If the server answers 401/403, use a `~/.netrc` with your Earthdata login instead; keep it out of the repo.)

Files go to `data/`, which is ignored by git. Never include a real Earthdata
token in commands committed to documentation, source files, or repository
configuration.
