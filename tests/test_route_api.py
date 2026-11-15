import sys
import types
from pathlib import Path

import pytest
import networkx as nx
from shapely.geometry import box

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import app as app_module  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(app_module, "OUTPUTS", ROOT / "outputs")
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_route_api_rejects_invalid_coordinates(client):
    response = client.post("/api/route", json={
        "origin": {"lon": "not-a-number", "lat": -25},
        "destination": {"lon": 32.2, "lat": -25.2},
    })
    assert response.status_code == 400
    assert response.get_json()["status"] == "invalid_input"


def test_route_api_reports_missing_cache(client, tmp_path, monkeypatch):
    stats = tmp_path / "stats.json"
    stats.write_text('{"bbox": [32, -26, 33.5, -24]}', encoding="utf-8")
    monkeypatch.setattr(app_module, "stats_path", lambda: stats)
    monkeypatch.setattr(app_module, "_route_files",
                        lambda: (tmp_path / "roads.graphml", tmp_path / "flood.geojson"))
    response = client.post("/api/route", json={
        "origin": {"lon": 32.1, "lat": -25.1},
        "destination": {"lon": 32.2, "lat": -25.2},
    })
    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "routing_unavailable"
    assert body["missing_artifacts"] == ["roads.graphml", "flood.geojson"]


def test_route_api_returns_normal_and_safe_routes(client, tmp_path, monkeypatch):
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:4326"
    graph.add_node(1, x=32.1, y=-25.1)
    graph.add_node(2, x=32.2, y=-25.1)
    graph.add_edge(1, 2, length=1000)
    graph.add_edge(2, 1, length=1000)
    graph_path = tmp_path / "roads.graphml"
    flood_path = tmp_path / "flood.geojson"
    graph_path.write_text("cached", encoding="utf-8")
    flood_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    monkeypatch.setattr(app_module, "_route_files", lambda: (graph_path, flood_path))
    fake_osmnx = types.SimpleNamespace(load_graphml=lambda path: graph)
    monkeypatch.setitem(sys.modules, "osmnx", fake_osmnx)
    stats = tmp_path / "stats.json"
    stats.write_text('{"bbox": [32, -26, 33.5, -24]}', encoding="utf-8")
    monkeypatch.setattr(app_module, "stats_path", lambda: stats)

    response = client.post("/api/route", json={
        "origin": {"lon": 32.1, "lat": -25.1},
        "destination": {"lon": 32.2, "lat": -25.1},
    })
    body = response.get_json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["normal"]["distance_m"] == 1000
    assert body["safe"]["distance_m"] == 1000


def test_route_api_rejects_points_outside_network_coverage(client, tmp_path, monkeypatch):
    import networkx as nx
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:4326"
    graph.add_node(1, x=32.1, y=-25.1)
    graph.add_node(2, x=32.2, y=-25.2)
    graph_path = tmp_path / "roads.graphml"
    flood_path = tmp_path / "flood.geojson"
    graph_path.write_text("cached", encoding="utf-8")
    flood_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    monkeypatch.setattr(app_module, "_route_files", lambda: (graph_path, flood_path))
    monkeypatch.setattr(app_module, "_load_route_data", lambda *_: (graph, box(0, 0, 1, 1)))
    stats = tmp_path / "stats.json"
    stats.write_text('{"bbox": [32, -26, 33.5, -24]}', encoding="utf-8")
    monkeypatch.setattr(app_module, "stats_path", lambda: stats)
    response = client.post("/api/route", json={
        "origin": {"lon": 32.1, "lat": -25.1},
        "destination": {"lon": 33.2, "lat": -24.2},
    })
    assert response.status_code == 503
    assert response.get_json()["status"] == "routing_unavailable"
