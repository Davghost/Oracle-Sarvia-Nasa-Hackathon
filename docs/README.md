# Project documentation

This folder holds the static copy of the app and the supporting
documentation. To read the Markdown files formatted, use the links on GitHub
or a local Markdown viewer.

## Start here

- [Project overview](project_overview.md): goal, scope, features and current
  status.
- [User guide](user_guide.md): how to go through the story, read the layers
  and use the route tool.
- [Concepts](concepts.md): NISAR, Copernicus, IoU, OpenStreetMap, detectable
  open water and potential impact explained.

## Technical documentation

- [Technical index](technical/README.md): reading path for installation and
  maintenance.
- [Architecture](technical/architecture.md): components and the flow between
  browser, Flask, pipeline and artefacts.
- [Data and methods](technical/data_and_methods.md): sources, definitions and
  how to read the results.
- [Pipeline](technical/pipeline.md): how to get, process and compare data.
- [Downloading the scenes](download.md): Earthdata authentication and getting
  the HDF5 files.
- [API and `stats.json` contract](stats_contract.md): the format the frontend
  reads, HTTP routes and optional layers.
- [Running and publishing](technical/deployment.md): local environment, GitHub
  Pages, the Flask server and configuration variables.
- [Development and maintenance](technical/development.md): repository
  structure, dependencies and check commands.

## Records and references

- [EMSR857 validation report](validation_report.md): compared product,
  metric, differences, limitations and the other sources searched.
- `h5_structure_17jan.txt` is an inspection dump of the NISAR HDF5 product,
  used as the reference for the file reader; not a narrative manual.
- `preview/` holds the QA images written by the detection (false colour,
  HH difference, histograms).

## Repository root

- [`README.md`](../README.md): the home page for whoever clones the project,
  including credits, data sources and licences.
- [`AI_USAGE_LOG.md`](../AI_USAGE_LOG.md): record of AI tool use in the
  project.
- [`LICENSE`](../LICENSE): Apache License 2.0 for our original code and
  content.
