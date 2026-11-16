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
    workspace = (DOCS / "workspace.html").read_text(encoding="utf-8")
    assert 'window.STATS_URL = "stats.json"' in page
    assert "static/app.js" in page
    assert "Comparação com mapa independente" in page
    assert "O que a inundação pode alcançar" in page
    assert "OpenStreetMap contributors" in page
    assert 'lang="pt"' in workspace
    assert "Explore impactos e rotas" in workspace
    assert 'id="route-osm-date"' in workspace
    assert 'id="validation-note"' in workspace

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

    # Exercise the Flask workspace route without binding a local TCP socket.
    response = build_static.app.test_client().get("/workspace")
    assert response.status_code == 200
    assert b"Explore impactos e rotas" in response.data
    assert b'id="route-osm-date"' in response.data


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
