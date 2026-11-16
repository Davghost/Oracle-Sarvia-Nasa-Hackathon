# Technical documentation

This set is for whoever installs, maintains or changes the system. The
[main README](../../README.md) remains the full description of the project;
this file organises the specialised technical reference.

## Components and contracts

- [Architecture](architecture.md): frontend, Flask, pipeline and publication.
- [Data and methods](data_and_methods.md): sources, metrics and
  interpretation.
- [API and `stats.json` contract](../stats_contract.md): endpoints and the
  format shared by backend, frontend and artefacts.

## Operation and development

- [Data pipeline](pipeline.md): download, processing and generation of
  results.
- [NISAR download](../download.md): Earthdata authentication and acquisition.
- [Running and publishing](deployment.md): local Flask, Pages, the live server
  and parameters.
- [Development and maintenance](development.md): dependencies, checks and
  practices for changes.

## Guidance for changes

Read the contract and the architecture before changing formats the frontend
reads. After changing templates, JavaScript, CSS or published data, rebuild
`docs/` with `python pipeline/build_static.py`. The static page does not run
the Flask API.
