import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from shapely.geometry import box

from routing_helpers import X0, Y0, at, grid_ways, pn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import app as app_module  # noqa: E402


def body(origin, destination, **extra):
    return {"origin": {"lon": origin[0], "lat": origin[1]},
            "destination": {"lon": destination[0], "lat": destination[1]}, **extra}


@pytest.fixture()
def network_file(tmp_path):
    flood = pn.FloodGeometry(box(X0 + 0.045, Y0 - 0.005, X0 + 0.055, Y0 + 0.075))
    arrays, meta = pn.build_network(grid_ways(), flood)
    return pn.save_network(tmp_path / "routing_network.npz", arrays, meta)


@pytest.fixture()
def client(monkeypatch, network_file):
    monkeypatch.setattr(app_module, "network_path", lambda: network_file)
    app_module._NETWORK.update(path=None, mtime=None, engine=None)
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_route_api_returns_fastest_and_dry_routes(client):
    r = client.post("/api/route", json=body(at(0, 0, dy=0.0002), at(10, 0, dy=0.0002)))
    data = r.get_json()
    assert r.status_code == 200 and data["status"] == "ok"
    assert data["normal"]["flooded_m"] > 900 and data["safe"]["flooded_m"] == 0
    assert data["safe"]["distance_m"] > data["normal"]["distance_m"]
    assert data["blocked_segments"] and data["origin"]["snapped"]
    assert data["crs"] == "EPSG:4326"


def test_route_api_accepts_list_coordinates(client):
    r = client.post("/api/route", json={"origin": list(at(1, 1)), "destination": list(at(3, 3))})
    assert r.status_code == 200


@pytest.mark.parametrize("payload", [
    None,
    {"origin": {"lon": "x", "lat": -25}, "destination": {"lon": 32.6, "lat": -25}},
    {"origin": {"lon": 32.5, "lat": -95}, "destination": {"lon": 32.6, "lat": -25}},
    {"origin": [32.5, -25], "destination": [32.6, -25], "alternatives": 9},
])
def test_route_api_rejects_invalid_input(client, payload):
    r = client.post("/api/route", json=payload) if payload is not None else \
        client.post("/api/route", data="not json", content_type="application/json")
    assert r.status_code == 400 and r.get_json()["status"] == "invalid_input"


def test_route_api_reports_points_outside_coverage(client):
    r = client.post("/api/route", json=body((33.4, -24.1), at(1, 1)))
    assert r.status_code == 422 and r.get_json()["status"] == "out_of_coverage"


def test_route_api_reports_missing_network(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "network_path", lambda: tmp_path / "missing.npz")
    r = client.post("/api/route", json=body(at(1, 1), at(2, 2)))
    data = r.get_json()
    assert r.status_code == 503 and data["status"] == "routing_unavailable"
    assert data["missing_artifacts"] == ["missing.npz"]
    assert "prepare_network.py" in data["error"]


def test_route_api_reports_unreadable_network(client, monkeypatch, tmp_path):
    broken = tmp_path / "broken.npz"
    broken.write_bytes(b"not a numpy file")
    monkeypatch.setattr(app_module, "network_path", lambda: broken)
    r = client.post("/api/route", json=body(at(1, 1), at(2, 2)))
    assert r.status_code == 503 and r.get_json()["status"] == "routing_unavailable"


def test_route_status_endpoint(client):
    data = client.get("/api/route/status").get_json()
    assert data["status"] == "ready" and data["network"]["nodes"] == 121


def test_route_api_sheds_load_when_busy(client, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(app_module, "_ROUTE_SLOTS", slots)
    r = client.post("/api/route", json=body(at(1, 1), at(2, 2)))
    assert r.status_code == 503 and r.get_json()["status"] == "busy"
    assert r.headers["Retry-After"] == "2"


def test_route_api_times_out_without_blocking_later_requests(client, monkeypatch):
    engine = app_module.get_network()
    real_route = engine.route

    def slow(*args, **kwargs):
        time.sleep(0.5)
        return real_route(*args, **kwargs)

    monkeypatch.setattr(engine, "route", slow)
    monkeypatch.setattr(app_module, "ROUTE_TIMEOUT_SECONDS", 0.05)
    r = client.post("/api/route", json=body(at(1, 1), at(2, 2)))
    assert r.status_code == 504 and r.get_json()["status"] == "routing_timeout"
    monkeypatch.setattr(engine, "route", real_route)
    monkeypatch.setattr(app_module, "ROUTE_TIMEOUT_SECONDS", 5)
    assert client.post("/api/route", json=body(at(1, 1), at(3, 2))).status_code == 200


def test_route_api_turns_engine_bugs_into_json_errors(client, monkeypatch):
    engine = app_module.get_network()
    monkeypatch.setattr(engine, "route", lambda *a, **k: 1 / 0)
    r = client.post("/api/route", json=body(at(1, 1), at(2, 2)))
    assert r.status_code == 500 and r.get_json()["status"] == "routing_error"


def test_route_api_handles_concurrent_requests(client):
    pairs = [(at(i % 10, 0, dy=0.0002), at(10 - i % 10, 10)) for i in range(40)]

    def call(pair):
        return client.post("/api/route", json=body(*pair))

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(call, pairs))
    assert all(r.status_code == 200 for r in responses)
    assert all(r.get_json()["normal"]["distance_m"] > 0 for r in responses)


def test_route_api_reloads_network_when_file_changes(client, network_file):
    first = app_module.get_network()
    arrays, meta = pn.build_network(grid_ways(n=5))
    pn.save_network(network_file, arrays, meta)
    second = app_module.get_network()
    assert second is not first and second.meta["nodes"] == 25


@pytest.fixture()
def lake_client(monkeypatch, tmp_path):
    from routing_helpers import water_grid
    lake = box(X0 + 0.045, Y0 + 0.025, X0 + 0.095, Y0 + 0.075)
    arrays, meta = pn.build_network(grid_ways(), pn.FloodGeometry(lake), water=water_grid(lake))
    path = pn.save_network(tmp_path / "lake.npz", arrays, meta)
    monkeypatch.setattr(app_module, "network_path", lambda: path)
    app_module._NETWORK.update(path=None, mtime=None, engine=None)
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_route_api_returns_rescue_route_into_the_flood(lake_client):
    r = lake_client.post("/api/route", json=body(at(0, 0), (X0 + 0.072, Y0 + 0.052)))
    data = r.get_json()
    assert r.status_code == 200 and data["recommended"] == "rescue"
    assert [leg["mode"] for leg in data["rescue"]["legs"]] == ["drive", "boat"]
    assert data["boat_assumptions"]["boat_speed_kmh"] == app_module.BOAT_SPEED_KMH


def test_route_api_can_exclude_boats(lake_client):
    r = lake_client.post("/api/route", json=body(at(0, 0), (X0 + 0.072, Y0 + 0.052), boats=False))
    data = r.get_json()
    assert r.status_code == 200 and data["rescue"] is None and data["boat_assumptions"] is None


def test_route_api_rejects_non_boolean_boats(lake_client):
    r = lake_client.post("/api/route", json=body(at(0, 0), at(3, 3), boats="yes"))
    assert r.status_code == 400 and r.get_json()["status"] == "invalid_input"


def test_route_status_reports_boat_layer(lake_client):
    info = lake_client.get("/api/route/status").get_json()["network"]
    assert info["boats"] is True and info["boat_cells"] > 0
