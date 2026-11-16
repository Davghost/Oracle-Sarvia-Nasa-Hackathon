# Development and maintenance

## Repository layout

- `app/`: Flask application, templates and Leaflet frontend.
- `pipeline/`: data download and processing, validation, OSM compilation and
  the route benchmark.
- `outputs/`: the contract and artefacts that feed the application.
- `docs/`: static site, manuals and work records.
- `tests/`: unit, integration and contract tests.
- `data/`: local scenes and working data, ignored by Git.

## Dependencies

- `requirements.txt`: server and route engine.
- `requirements-pipeline.txt`: geospatial processing, data and QA tools.

Use the project's virtual environment. Install the pipeline dependencies only
when you need to download or process sources or run offline routines.

## Checks

To run the full suite:

```bash
python -m pytest
```

Some tests on real artefacts may be skipped when HDF5 files, the OSM extract
or other local data are missing. Read the reason for each skip in the output;
a skipped test does not prove the pipeline on real data.

## When changing the project

1. Keep the JSON contract between pipeline, Flask and frontend.
2. Update `docs/stats_contract.md` when you change fields, layers or
   endpoints.
3. Rebuild `docs/` after changing templates, JavaScript, CSS or outputs the
   static site reads.
4. Update the overview, concepts or user guide pages if you change a
   definition that affects how users read the results.
5. Keep the limitations next to the results: estimates are not confirmed
   damage, and experimental routes do not replace official guidance.
6. Do not commit tokens, private HDF5 files or disposable intermediates.
7. Record AI tool use in `AI_USAGE_LOG.md`, and credit any new data, code or
   asset with its licence in the README.

## Canonical sources

For current behaviour, prefer the code and the files `outputs/stats.json` and
`docs/stats_contract.md`. Dated reports are historical snapshots; do not use
them as the current state without comparing them with the artefacts present.
