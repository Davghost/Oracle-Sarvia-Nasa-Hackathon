# Downloading the GCOV scenes

Each GCOV file is about 3.8 GB. On a slow home connection it takes ~4 h each, so download in the Codespace.

1. Store the Earthdata token as a Codespaces secret named `EARTHDATA_TOKEN` (never in the repo).
2. `pip install asf_search` then `python pipeline/download_gcov.py` (not tested yet; fix it if the API differs).

## Fallback with wget

Copy each scene's download URL from ASF Vertex, then in the Codespace:

```bash
wget --header="Authorization: Bearer $EARTHDATA_TOKEN" -P data/ "<URL_FROM_VERTEX>"
```

(If the server answers 401/403, use a `~/.netrc` with your Earthdata login instead; keep it out of the repo.)

Files go to `data/`, which is ignored by git.
