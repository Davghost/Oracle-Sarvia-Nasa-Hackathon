import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import validate_reference  # noqa: E402


def feature(geometry, properties=None):
    return {
        "type": "Feature",
        "properties": properties or {},
        "geometry": geometry.__geo_interface__,
    }


def make_reference_zip(path, aoi, flood, non_flood=None):
    product = io.BytesIO()
    with ZipFile(product, "w") as archive:
        archive.writestr(
            "EMSR857_AOI02_FEP_PRODUCT_areaOfInterestA_v1.json",
            json.dumps({"type": "FeatureCollection", "features": [feature(aoi)]}),
        )
        events = [feature(flood, {"event_type": "5-Flood"})]
        if non_flood is not None:
            events.append(feature(non_flood, {"event_type": "2-Other"}))
        archive.writestr(
            "EMSR857_AOI02_FEP_PRODUCT_observedEventA_v1.json",
            json.dumps({"type": "FeatureCollection", "features": events}),
        )
    with ZipFile(path, "w") as archive:
        archive.writestr("EMSR857_AOI02_FEP_PRODUCT_v1.zip", product.getvalue())


def test_compare_geometries_clips_both_layers_to_aoi():
    aoi = box(32.0, -25.1, 32.1, -25.0)
    mask = box(31.99, -25.08, 32.06, -25.02)
    reference = box(31.99, -25.08, 32.06, -25.02)

    result = validate_reference.compare_geometries(mask, reference, aoi, 1)
    clipped_area = validate_reference.project_to_metric(
        box(32.0, -25.08, 32.06, -25.02),
        validate_reference.metric_epsg(aoi),
    ).area / 1_000_000

    assert result["iou"] == 1
    assert result["overlap_fraction_nisar"] == 1
    assert result["overlap_fraction_ems"] == 1
    assert result["nisar_new_water_aoi_km2"] == pytest.approx(clipped_area, abs=0.001)
    assert result["reference_feature_count"] == 1


def test_invalid_input_geometry_is_repaired_and_reported():
    bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
    document = {"type": "FeatureCollection", "features": [feature(bowtie)]}

    geometries, repaired = validate_reference.read_feature_collection(document, "test mask")

    assert repaired == 1
    assert geometries[0].is_valid


def test_main_adds_reference_metrics_to_real_stats_only(tmp_path, monkeypatch):
    aoi = box(32.0, -25.1, 32.1, -25.0)
    flood = box(32.02, -25.08, 32.08, -25.02)
    mask_path = tmp_path / "flood_extent.geojson"
    mask_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [feature(flood)],
    }))
    reference_path = tmp_path / "reference.zip"
    make_reference_zip(reference_path, aoi, flood, box(32.01, -25.09, 32.02, -25.08))
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(json.dumps({"mock": False, "layers": {}}))
    monkeypatch.setattr(
        "sys.argv",
        [
            "validate_reference.py",
            "--stats", str(stats_path),
            "--mask", str(mask_path),
            "--reference", str(reference_path),
        ],
    )

    validate_reference.main()

    stats = json.loads(stats_path.read_text())
    assert stats["validation"]["iou"] == 1
    assert stats["validation"]["reference_feature_count"] == 1


def test_main_refuses_mock_stats_without_modifying_them(tmp_path, monkeypatch):
    stats_path = tmp_path / "stats.json"
    original = {"mock": True, "layers": {}}
    stats_path.write_text(json.dumps(original))
    monkeypatch.setattr(
        "sys.argv",
        ["validate_reference.py", "--stats", str(stats_path)],
    )

    with pytest.raises(SystemExit) as exc:
        validate_reference.main()

    assert exc.value.code == 2
    assert json.loads(stats_path.read_text()) == original
