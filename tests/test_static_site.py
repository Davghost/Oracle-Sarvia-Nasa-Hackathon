import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "pipeline"))
import build_static  # noqa: E402


def test_static_site_serves_pages_stats_and_prebuilt_layers():
    page = (DOCS / "index.html").read_text(encoding="utf-8")
    tool = (DOCS / "routes.html").read_text(encoding="utf-8")
    for html in (page, tool):
        assert 'window.STATS_URL = "stats.json"' in html
        assert 'window.SARVIA_ROUTES_URL = "routes.html"' in html
        assert "static/core.js" in html
        assert 'lang="en"' in html
        assert "OpenStreetMap contributors" in html
    # the story: five screens, the last one leads to the route tool
    assert page.count('class="step"') == 5
    assert "static/story.js" in page
    assert "What the flood may reach" in page
    assert "Checked against an independent map" in page
    assert 'id="routes-cta" href="routes.html"' in page
    # the tool: planner, places, layer tree and map styles in the side panel
    assert "static/routes.js" in tool
    for element in ("route-origin", "place-search", "layer-tree", "basemaps", "route-osm-date", "static-route-note"):
        assert f'id="{element}"' in tool
    assert 'url=routes.html' in (DOCS / "workspace.html").read_text(encoding="utf-8")

    stats = json.loads((DOCS / "stats.json").read_text(encoding="utf-8"))
    assert stats["mock"] is False
    assert stats["validation"]["iou"] == 0.4616
    assert stats["impact"]["categories"]["school"]["total"] > 0
    assert {"impact_features", "impact_roads", "validation_difference"} <= set(stats["layers"])
    for layer in stats["layers"].values():
        asset = DOCS / layer["url"]
        assert asset.is_file()
        if layer["type"] == "geojson":
            assert json.loads(asset.read_text(encoding="utf-8"))["type"] == "FeatureCollection"
        elif layer["type"] != "image":
            pytest.fail(f"unsupported static layer type: {layer['type']}")
    assert (DOCS / "how-to-read-radar.html").is_file()

    # Exercise the Flask pages without binding a local TCP socket.
    client = build_static.app.test_client()
    response = client.get("/routes")
    assert response.status_code == 200
    assert b"Route tool" in response.data
    assert b'id="route-planner-controls"' in response.data
    assert b'window.SARVIA_ROUTES_URL = "/routes"' in response.data
    story = client.get("/")
    assert story.status_code == 200
    assert b'id="routes-cta" href="/routes"' in story.data
    old = client.get("/workspace")
    assert old.status_code == 301
    assert old.headers["Location"].endswith("/routes")


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
            "impact_features": {"type": "geojson", "url": "/outputs/impact_features.geojson"},
            "impact_roads": {"type": "geojson", "url": "/outputs/impact_roads.geojson"},
            "validation_difference": {"type": "geojson", "url": "/outputs/validation_difference.geojson"},
        },
    }))
    for name in ("impact_features", "impact_roads", "validation_difference"):
        (outputs / f"{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    monkeypatch.setattr(build_static, "ROOT", root)
    monkeypatch.setattr(build_static, "DOCS", docs)

    build_static.main()

    built_stats = json.loads((docs / "stats.json").read_text())
    for name in ("impact_features", "impact_roads"):
        assert built_stats["layers"][name]["url"] == f"outputs/{name}.geojson"
        assert json.loads((docs / "outputs" / f"{name}.geojson").read_text())["type"] == "FeatureCollection"
    assert built_stats["layers"]["validation_difference"]["url"] == (
        "outputs/validation_difference.geojson"
    )
    assert json.loads(
        (docs / "outputs" / "validation_difference.geojson").read_text()
    )["type"] == "FeatureCollection"
