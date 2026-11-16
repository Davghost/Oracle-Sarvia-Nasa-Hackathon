"""Flask app: serves pre-computed results and the flood-aware route API.

No heavy processing happens here: the road network is compiled offline by
pipeline/prepare_network.py and loaded once (about a second) on first use.
"""
import json
import os
import sys
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import routing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

app = Flask(__name__)
MAX_TILE_BYTES = 8 * 1024 * 1024

DEFAULT_SATELLITE_TILE_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
    "MapServer/tile/{z}/{y}/{x}"
)
DEFAULT_HYBRID_TILE_URL = DEFAULT_SATELLITE_TILE_URL
DEFAULT_HYBRID_LABELS_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/"
    "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
)


def map_config():
    """Expose public map metadata; configured provider URLs stay server-side."""
    satellite_url = os.environ.get("SARVIA_SATELLITE_TILE_URL")
    hybrid_url = os.environ.get("SARVIA_HYBRID_TILE_URL")
    config = {
        "satellite": True,
        "hybrid": True,
        "attribution": {
            "satellite": os.environ.get("SARVIA_SATELLITE_ATTRIBUTION", "© Esri"),
            "hybrid": os.environ.get(
                "SARVIA_HYBRID_ATTRIBUTION",
                "© Esri | © OpenStreetMap contributors",
            ),
        },
    }
    config["satellite_url"] = (
        "/map-tiles/satellite/{z}/{x}/{y}" if satellite_url else DEFAULT_SATELLITE_TILE_URL
    )
    config["hybrid_url"] = (
        "/map-tiles/hybrid/{z}/{x}/{y}" if hybrid_url else DEFAULT_HYBRID_TILE_URL
    )
    config["hybrid_labels_url"] = DEFAULT_HYBRID_LABELS_URL if not hybrid_url else ""
    return config

# Route API settings (environment variables, all optional).
ROUTE_WORKERS = max(1, int(os.environ.get("SARVIA_ROUTE_WORKERS", "2")))
ROUTE_MAX_PENDING = max(1, int(os.environ.get("SARVIA_ROUTE_MAX_PENDING", "16")))
ROUTE_TIMEOUT_SECONDS = float(os.environ.get("SARVIA_ROUTE_TIMEOUT", "12"))
ROUTE_MAX_SNAP_M = float(os.environ.get("SARVIA_ROUTE_MAX_SNAP_M", "1500"))
ROUTE_BLOCK_FLOOD_M = float(os.environ.get("SARVIA_ROUTE_BLOCK_FLOOD_M", "0"))
BOAT_SPEED_KMH = float(os.environ.get("SARVIA_BOAT_SPEED_KMH", str(routing.BOAT_SPEED_KMH)))
BOAT_LAUNCH_MIN = float(os.environ.get("SARVIA_BOAT_LAUNCH_MIN", str(routing.BOAT_LAUNCH_S / 60)))

_ROUTE_EXECUTOR = ThreadPoolExecutor(max_workers=ROUTE_WORKERS, thread_name_prefix="route")
_ROUTE_SLOTS = threading.BoundedSemaphore(ROUTE_MAX_PENDING)
_NETWORK_LOCK = threading.Lock()
_NETWORK = {"path": None, "mtime": None, "engine": None}


def stats_path() -> Path:
    """Real results win; fall back to mock data while the pipeline is not ready."""
    # Keeping the fallback in the server makes the interface usable before a
    # pipeline run, while a generated real result always takes precedence.
    real = OUTPUTS / "stats.json"
    return real if real.exists() else OUTPUTS / "mock" / "stats.json"


@app.get("/")
def index():
    """Render the five-screen flood story."""
    return render_template("index.html", map_config=map_config(), page="story")


@app.get("/routes")
def routes():
    """Render the route tool: the operational map with layers, places and routes."""
    return render_template("routes.html", map_config=map_config(), page="routes")


@app.get("/workspace")
def workspace():
    """Old address of the impact and route workspace, kept so links still work."""
    return redirect(url_for("routes"), code=301)


@app.get("/how-to-read-radar")
def how_to_read_radar():
    """Render the explanatory page about SAR interpretation."""
    return render_template("radar.html")


@app.get("/map-tiles/<provider>/<int:z>/<int:x>/<int:y>")
def map_tiles(provider, z, x, y):
    """Proxy configured provider tiles so credentials never reach the browser."""
    defaults = {
        "satellite": DEFAULT_SATELLITE_TILE_URL,
        "hybrid": DEFAULT_HYBRID_TILE_URL,
    }
    template = os.environ.get(f"SARVIA_{provider.upper()}_TILE_URL", defaults.get(provider))
    if not template or provider not in {"satellite", "hybrid"}:
        abort(404)
    if z > 22 or x >= 2 ** z or y >= 2 ** z:
        abort(404)
    try:
        url = template.format(z=z, x=x, y=y, s="a")
    except (KeyError, ValueError):
        app.logger.error("invalid tile URL template for %s", provider)
        abort(502)
    try:
        with urlopen(Request(url, headers={"User-Agent": "SarvIA/1.0"}), timeout=10) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"image/png", "image/jpeg", "image/webp"}:
                abort(502)
            payload = response.read(MAX_TILE_BYTES + 1)
    except (HTTPError, URLError, ValueError) as exc:
        app.logger.warning("map tile unavailable for %s: %s", provider, exc)
        abort(502)
    if len(payload) > MAX_TILE_BYTES:
        abort(502)
    return app.response_class(payload, content_type=content_type,
                              headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/stats")
def api_stats():
    """Return the JSON contract consumed by the browser application."""
    path = stats_path()
    if not path.exists():
        abort(404, "stats.json not found")
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


def network_path() -> Path:
    """Compiled road network written by pipeline/prepare_network.py."""
    custom = os.environ.get("SARVIA_ROUTING_NETWORK")
    return Path(custom) if custom else OUTPUTS / "routing_network.npz"


def get_network():
    """Load the routing engine once per process; reload if the file changes."""
    path = network_path()
    if not path.exists():
        return None
    mtime = path.stat().st_mtime_ns
    with _NETWORK_LOCK:
        if _NETWORK["engine"] is None or _NETWORK["path"] != path or _NETWORK["mtime"] != mtime:
            engine = routing.RoutingNetwork.load(
                path, max_snap_m=ROUTE_MAX_SNAP_M, block_flood_m=ROUTE_BLOCK_FLOOD_M,
                boat_speed_kmh=BOAT_SPEED_KMH, launch_minutes=BOAT_LAUNCH_MIN)
            _NETWORK.update(path=path, mtime=mtime, engine=engine)
        return _NETWORK["engine"]


def _unavailable(message, status=503, **extra):
    return jsonify({"status": "routing_unavailable", "error": message, **extra}), status


@app.get("/api/route/status")
def api_route_status():
    """Report whether routing is ready and describe the loaded network."""
    try:
        engine = get_network()
    except (OSError, ValueError, KeyError) as exc:
        return _unavailable(f"The road network file could not be read: {exc}")
    if engine is None:
        return _unavailable(
            "No road network has been prepared. Run: python pipeline/prepare_network.py --download",
            missing_artifacts=[network_path().name])
    return jsonify({"status": "ready", "network": engine.info(),
                    "workers": ROUTE_WORKERS, "timeout_s": ROUTE_TIMEOUT_SECONDS})


@app.post("/api/route")
def api_route():
    """Rescue (car + boat), flood-avoiding, fastest and alternative routes between two WGS84 points."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "invalid_input",
                        "error": "Send JSON: {\"origin\": {\"lon\", \"lat\"}, \"destination\": {...}}"}), 400
    try:
        origin = routing.validate_point(payload.get("origin"), "origin")
        destination = routing.validate_point(payload.get("destination"), "destination")
        alternatives = payload.get("alternatives", 2)
        if isinstance(alternatives, bool) or not isinstance(alternatives, int) or not 0 <= alternatives <= 3:
            raise routing.RouteError("invalid_input", "alternatives must be an integer from 0 to 3", 400)
        boats = payload.get("boats", True)
        if not isinstance(boats, bool):
            raise routing.RouteError("invalid_input", "boats must be true or false", 400)
    except routing.RouteError as exc:
        return jsonify(exc.to_json()), exc.http_status

    try:
        engine = get_network()
    except (OSError, ValueError, KeyError) as exc:
        return _unavailable(f"The road network file could not be read: {exc}")
    if engine is None:
        return _unavailable(
            "No road network has been prepared. Run: python pipeline/prepare_network.py --download",
            missing_artifacts=[network_path().name])

    # Bounded queue: under overload answer at once instead of piling up requests.
    if not _ROUTE_SLOTS.acquire(blocking=False):
        response = jsonify({"status": "busy", "error": "Too many route requests at once. Try again in a moment."})
        response.headers["Retry-After"] = "2"
        return response, 503
    try:
        future = _ROUTE_EXECUTOR.submit(engine.route, origin, destination, alternatives, boats)
    except RuntimeError as exc:
        _ROUTE_SLOTS.release()
        return _unavailable(str(exc))
    # The slot is released when the computation really ends, not at timeout,
    # so slow searches can never accumulate beyond ROUTE_MAX_PENDING.
    future.add_done_callback(lambda _: _ROUTE_SLOTS.release())
    try:
        result = future.result(timeout=ROUTE_TIMEOUT_SECONDS)
    except TimeoutError:
        return jsonify({"status": "routing_timeout",
                        "error": f"The route search took longer than {ROUTE_TIMEOUT_SECONDS:.0f} seconds."}), 504
    except routing.RouteError as exc:
        return jsonify(exc.to_json()), exc.http_status
    except Exception as exc:  # report engine bugs as JSON instead of an HTML 500 page
        app.logger.exception("route computation failed")
        return jsonify({"status": "routing_error", "error": "Route computation failed unexpectedly."}), 500
    return jsonify(result)


@app.get("/outputs/<path:name>")
def outputs(name):
    """Serve the generated overlay files used by the map."""
    return send_from_directory(OUTPUTS, name)


if __name__ == "__main__":
    # Warm the routing engine in the background so the first route is fast.
    threading.Thread(target=lambda: network_path().exists() and get_network(), daemon=True).start()
    # Keep the interactive debugger off by default, including on a public bind.
    # Enable it explicitly only during local development with FLASK_DEBUG=1.
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
