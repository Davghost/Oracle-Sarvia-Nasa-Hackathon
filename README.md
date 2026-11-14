# The Algorithm's Oracle

NASA Space Apps Challenge 2026 · challenge **Dancing with the SARs**.

Interactive map of the January 2026 flood in southern Mozambique (Limpopo and Incomati basins) seen by the NISAR L-band radar: before/during slider and flooded area in km².

> NISAR data used here are **provisional** and may be reprocessed. The app currently runs on **mock data** until the real pipeline output is ready.

## Run the app

```bash
pip install -r requirements.txt
python app/app.py
```

Open http://localhost:5000

## Layout

- `app/`: Flask app (serves pre-computed results only)
- `pipeline/`: offline processing (download, crop, dB, water detection, export)
- `outputs/`: light results used by the app (`stats.json`, layers). `outputs/mock/` is fake data for UI work
- `docs/`: notes and the `stats.json` contract
- `data/`: raw NISAR files. **Never committed** (see `.gitignore`)

Project memory for the team: `PROJECT_CONTEXT.md`. Tasks: `TASKS.xlsx`. AI use: `AI_USAGE_LOG.md`.

Never commit credentials, tokens or HDF5 files.
