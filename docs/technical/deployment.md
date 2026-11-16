# Running and publishing

## Local development

Server dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python app/app.py
```

Open `http://localhost:5000`. To run the offline pipeline, also install
`requirements-pipeline.txt`. The versioned compiled network lets the planner
load without downloading the OSM extract again.

Flask debug mode is off by default. To turn it on during local development,
set `FLASK_DEBUG=1`; do not enable the debugger on a public deployment.

## The live server

The public app at <https://sarvia.duckdns.org> runs on an Oracle Cloud
Always Free VM (Ubuntu 24.04):

- the app in `/opt/sarvia` with its own virtual environment;
- a systemd service, `sarvia.service`, running Gunicorn with one worker and
  four threads (`--preload`, bound to `127.0.0.1:8000`), so the route network
  is loaded once;
- Nginx as the public reverse proxy, with gzip;
- a Let's Encrypt certificate from certbot, with HTTP redirected to HTTPS and
  automatic renewal;
- the `sarvia.duckdns.org` name from DuckDNS.

To update it after pushing to `main` (the SSH key stays on the maintainer's
machine and is never committed):

```bash
ssh -i <path-to-key> ubuntu@<server> "cd /opt/sarvia && git pull && .venv/bin/pip install -q -r requirements.txt && sudo systemctl restart sarvia"
```

## GitHub Pages

The `docs/` folder is published as a static site. To rebuild it:

```bash
python pipeline/build_static.py
```

In the GitHub repository, set Pages to publish `main` and `/docs` (or the
branch and folder the maintainer chooses). Changes only appear after the
commit with the generated files reaches the publishing source and the Pages
workflow finishes.

Pages does not run Flask, does not expose `/api/route`, does not load a route
network on a server and cannot keep provider secrets behind a proxy. So the
route tool's planner is replaced by a note and a link to the live tool; the
layers, places and filters still work.

## Basemaps and the tile proxy

The frontend offers light and dark maps plus satellite and hybrid options.
The default satellite and hybrid URLs use Esri; external services can vary in
coverage, terms, attribution and availability.

In Flask, these optional variables set XYZ URLs and credits:

| Variable | Use |
|---|---|
| `SARVIA_SATELLITE_TILE_URL` | Private XYZ URL for the satellite map. |
| `SARVIA_HYBRID_TILE_URL` | Private XYZ URL for the hybrid raster layer. |
| `SARVIA_SATELLITE_ATTRIBUTION` | Attribution required for satellite. |
| `SARVIA_HYBRID_ATTRIBUTION` | Attribution required for hybrid. |

When a private URL is set, Flask fetches it under `/map-tiles/...` so the
secret is not published in the browser. Keep tokens in the hosting service's
secret manager; never write them in HTML, JavaScript, `stats.json` or Git. The
static copy does not use the proxy.

## Route parameters

All optional. The values below are the current server defaults:

| Variable | Default | Effect |
|---|---:|---|
| `SARVIA_ROUTING_NETWORK` | `outputs/routing_network.npz` | Path to the compiled network. |
| `SARVIA_ROUTE_WORKERS` | `2` | Simultaneous route computations in the pool. |
| `SARVIA_ROUTE_MAX_PENDING` | `16` | Limit of requests in the queue; the rest get `busy`. |
| `SARVIA_ROUTE_TIMEOUT` | `12` s | Maximum time the API waits for a computation. |
| `SARVIA_ROUTE_MAX_SNAP_M` | `1500` m | Maximum distance to attach a point to the road network. |
| `SARVIA_ROUTE_BLOCK_FLOOD_M` | `0` m | Water tolerated per segment on a route classed as dry. |
| `SARVIA_BOAT_SPEED_KMH` | `12` | Assumed boat speed on open water. |
| `SARVIA_BOAT_LAUNCH_MIN` | `10` min | Assumed time to launch the boat. |

See the [API contract](../stats_contract.md) before changing the response
format.
