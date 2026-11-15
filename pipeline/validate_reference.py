"""Compare the NISAR new-water mask with the EMSR857 AOI02 flood vector."""
import argparse
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import geopandas as gpd
from shapely import make_valid
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
AOI_FILE = "areaOfInterestA_v1.json"
EVENT_FILE = "observedEventA_v1.json"
PRODUCT_ZIP = "AOI02_FEP_PRODUCT_v1.zip"


def read_feature_collection(document, description):
    if document.get("type") != "FeatureCollection":
        raise ValueError(f"{description} must be a GeoJSON FeatureCollection")
    source_geometries = [
        shape(feature["geometry"])
        for feature in document.get("features", [])
        if feature.get("geometry")
    ]
    if not source_geometries:
        raise ValueError(f"{description} contains no geometries")
    repaired_count = 0
    geometries = []
    for geometry in source_geometries:
        if not geometry.is_valid:
            geometry = make_valid(geometry)
            repaired_count += 1
        if not geometry.is_valid:
            raise ValueError(f"{description} contains an unrepairable geometry")
        geometries.append(geometry)
    return geometries, repaired_count


def read_reference(reference_zip):
    with ZipFile(reference_zip) as archive:
        product_entries = [
            item.filename for item in archive.infolist()
            if PurePosixPath(item.filename).name.endswith(PRODUCT_ZIP)
        ]
        if len(product_entries) != 1:
            raise ValueError(f"expected one AOI02 FEP product ZIP, found {len(product_entries)}")
        product_bytes = archive.read(product_entries[0])

    with ZipFile(BytesIO(product_bytes)) as product:
        def read_layer(suffix):
            entries = [
                item.filename for item in product.infolist()
                if PurePosixPath(item.filename).name.endswith(suffix)
            ]
            if len(entries) != 1:
                raise ValueError(f"expected one {suffix}, found {len(entries)}")
            return json.loads(product.read(entries[0]))

        aoi_document = read_layer(AOI_FILE)
        event_document = read_layer(EVENT_FILE)

    aoi_features = aoi_document.get("features", [])
    if len(aoi_features) != 1 or not aoi_features[0].get("geometry"):
        raise ValueError("AOI02 file must contain one polygon geometry")
    aoi = shape(aoi_features[0]["geometry"])
    aoi_repaired = not aoi.is_valid
    if aoi_repaired:
        aoi = make_valid(aoi)
    if not aoi.is_valid:
        raise ValueError("AOI02 geometry is unrepairable")

    event_features = [
        feature for feature in event_document.get("features", [])
        if feature.get("properties", {}).get("event_type") == "5-Flood"
    ]
    geometries, event_repairs = read_feature_collection(
        {"type": "FeatureCollection", "features": event_features},
        "EMSR857 observedEventA flood layer",
    )
    return aoi, unary_union(geometries), len(geometries), event_repairs + int(aoi_repaired)


def metric_epsg(geometry):
    lon, lat = geometry.centroid.x, geometry.centroid.y
    zone = int((lon + 180) // 6) + 1
    return 32700 + zone if lat < 0 else 32600 + zone


def project_to_metric(geometry, epsg):
    return gpd.GeoSeries([geometry], crs="EPSG:4326").to_crs(epsg=epsg).iloc[0]


def compare_geometries(mask, reference, aoi, feature_count, geometry_repairs=0):
    epsg = metric_epsg(aoi)
    mask_clipped = project_to_metric(mask.intersection(aoi), epsg)
    reference_clipped = project_to_metric(reference.intersection(aoi), epsg)
    intersection = mask_clipped.intersection(reference_clipped)
    system_only = mask_clipped.difference(reference_clipped)
    reference_only = reference_clipped.difference(mask_clipped)
    intersection_area = intersection.area / 1_000_000
    mask_area = mask_clipped.area / 1_000_000
    reference_area = reference_clipped.area / 1_000_000
    union_area = mask_clipped.union(reference_clipped).area / 1_000_000
    if min(mask_area, reference_area, union_area) <= 0:
        raise ValueError("AOI02 comparison contains an empty or zero-area geometry")

    def difference_feature(geometry, classification, source):
        if geometry.is_empty or geometry.area <= 0:
            return None
        geographic = gpd.GeoSeries([geometry], crs=f"EPSG:{epsg}").to_crs(
            epsg=4326
        ).iloc[0]
        geographic = geographic.simplify(20, preserve_topology=True)
        if geographic.is_empty:
            return None
        return {
            "type": "Feature",
            "properties": {"classification": classification, "source": source},
            "geometry": mapping(geographic),
        }

    difference_features = [
        feature for feature in (
            difference_feature(system_only, "system_only", "NISAR GCOV"),
            difference_feature(reference_only, "reference_only", "Copernicus EMS"),
        ) if feature is not None
    ]
    return {
        "reference": "Copernicus EMSR857 AOI02 Massiguita",
        "reference_url": "https://mapping.emergency.copernicus.eu/activations/EMSR857/",
        "product": "FEP observedEventA, event_type 5-Flood",
        "acquisition_utc": "2026-01-17T03:19:00Z",
        "metric_crs": f"EPSG:{epsg}",
        "reference_feature_count": feature_count,
        "geometry_repairs": geometry_repairs,
        "nisar_new_water_aoi_km2": round(mask_area, 3),
        "ems_flood_area_aoi_km2": round(reference_area, 3),
        "intersection_area_km2": round(intersection_area, 3),
        "union_area_km2": round(union_area, 3),
        "system_only_area_km2": round(system_only.area / 1_000_000, 3),
        "reference_only_area_km2": round(reference_only.area / 1_000_000, 3),
        "iou": round(intersection_area / union_area, 4),
        "overlap_fraction_nisar": round(intersection_area / mask_area, 4),
        "overlap_fraction_ems": round(intersection_area / reference_area, 4),
        "difference_features": difference_features,
        "interpretation": (
            "Spatial agreement only, not ground truth: NISAR new water is relative "
            "to 2026-01-05; EMS maps semi-automatically extracted flooded area."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", type=Path, default=ROOT / "outputs" / "stats.json")
    parser.add_argument("--mask", type=Path, default=ROOT / "outputs" / "flood_extent.geojson")
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "data" / "reference" / "EMSR857_products.zip",
    )
    args = parser.parse_args()

    if not args.stats.exists():
        parser.error(f"stats file not found: {args.stats}")
    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    if stats.get("mock") is not False:
        parser.error("reference validation requires real stats.json with mock: false")

    try:
        mask_document = json.loads(args.mask.read_text(encoding="utf-8"))
        mask_geometries, mask_repairs = read_feature_collection(mask_document, "NISAR mask")
        mask = unary_union(mask_geometries)
        aoi, reference, count, reference_repairs = read_reference(args.reference)
        stats["validation"] = compare_geometries(
            mask, reference, aoi, count, mask_repairs + reference_repairs
        )
        differences = stats["validation"].pop("difference_features")
    except (OSError, KeyError, ValueError, BadZipFile) as exc:
        parser.error(f"could not validate EMSR857: {exc}")

    difference_path = args.stats.parent / "validation_difference.geojson"
    difference_path.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": differences},
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    stats.setdefault("layers", {})["validation_difference"] = {
        "type": "geojson",
        "url": "/outputs/validation_difference.geojson",
    }
    args.stats.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result = stats["validation"]
    print(
        f"saved {args.stats}: IoU {result['iou']:.4f}, "
        f"{result['intersection_area_km2']:.3f} km2 overlap in {result['metric_crs']}"
    )


if __name__ == "__main__":
    main()
