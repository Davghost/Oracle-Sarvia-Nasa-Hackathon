import json
import shutil
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "pipeline"))
import build_static  # noqa: E402


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def test_static_site_serves_pages_stats_and_prebuilt_layers():
    handler = partial(QuietHandler, directory=str(DOCS))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(f"{base_url}/") as response:
            page = response.read().decode("utf-8")
            assert response.status == 200
            assert 'window.STATS_URL = "stats.json"' in page
            assert "static/app.js" in page
            assert "Independent map comparison" in page

        with urlopen(f"{base_url}/stats.json") as response:
            stats = json.load(response)
            assert response.status == 200
            assert stats["mock"] is False
            assert stats["validation"]["iou"] == 0.4616

        for layer in stats["layers"].values():
            with urlopen(f"{base_url}/{layer['url']}") as response:
                assert response.status == 200
                if layer["type"] == "image":
                    assert response.headers["Content-Type"] == "image/png"
                elif layer["type"] == "geojson":
                    assert json.loads(response.read())["type"] == "FeatureCollection"
                else:
                    pytest.fail(f"unsupported static layer type: {layer['type']}")

        with urlopen(f"{base_url}/how-to-read-radar.html") as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_static_build_copies_optional_geojson_layer(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parent.parent
    root = tmp_path / "repo"
    docs = root / "docs"
    outputs = root / "outputs"
    docs.mkdir(parents=True)
    outputs.mkdir()
    (root / "app").mkdir()
    shutil.copytree(repo / "app" / "static", root / "app" / "static")
    (outputs / "stats.json").write_text(json.dumps({
        "mock": False,
        "layers": {
            "roads_blocked": {
                "type": "geojson",
                "url": "/outputs/roads_blocked.geojson",
            },
            "validation_difference": {
                "type": "geojson",
                "url": "/outputs/validation_difference.geojson",
            },
        },
    }))
    (outputs / "roads_blocked.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [],
    }))
    (outputs / "validation_difference.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"classification": "system_only"},
            "geometry": {"type": "Polygon", "coordinates": []},
        }],
    }))
    monkeypatch.setattr(build_static, "ROOT", root)
    monkeypatch.setattr(build_static, "DOCS", docs)

    build_static.main()

    built_stats = json.loads((docs / "stats.json").read_text())
    assert built_stats["layers"]["roads_blocked"]["url"] == "outputs/roads_blocked.geojson"
    assert built_stats["layers"]["validation_difference"]["url"] == (
        "outputs/validation_difference.geojson"
    )
    assert json.loads((docs / "outputs" / "roads_blocked.geojson").read_text())["type"] == "FeatureCollection"
    assert json.loads(
        (docs / "outputs" / "validation_difference.geojson").read_text()
    )["features"][0]["properties"]["classification"] == "system_only"
