# Independent validation reference

## Result

**Chosen reference:** Copernicus Emergency Management Service (EMS) Rapid
Mapping, activation [EMSR857](https://mapping.emergency.copernicus.eu/activations/EMSR857/),
product AOI02 Massiguita, type FEP, Sentinel-1 image acquired on
**17 Jan 2026 at 03:19 UTC**:

`EMSR857_AOI02_FEP_PRODUCT_SENTINEL1_20260117_0319_ORTHO.tif`

The official catalogue lists the activation as a flood in Mozambique and South
Africa, starting on 17 Jan 2026 at 07:38 UTC, and lists the product above
under the Massiguita AOI. The AOI geometry intersects the NISAR polygon of new
detectable open water. The Sentinel-1 acquisition is from the same day as the
NISAR scene of 17 Jan 2026 at 03:42 UTC, about 23 minutes earlier. This
closeness in time and the spatial overlap make it the best candidate found for
the comparison.

Metadata and the package download are published in the
[EMSR857 activation record](https://mapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR857);
the product package is listed as
[`EMSR857_products.zip`](https://rapidmapping.emergency.copernicus.eu/backend/EMSR857/EMSR857_products.zip).
It was downloaded to `data/reference/EMSR857_products.zip` (473,423,693 bytes;
ignored by Git) and passed the CRC check, as did the AOI02 FEP product ZIP
inside it. The AOI02 package holds the AOI boundary and the vector layer
`observedEventA`, but **not the Sentinel-1 GeoTIFF**
`EMSR857_AOI02_FEP_PRODUCT_SENTINEL1_20260117_0319_ORTHO.tif` named as the
source image in the catalogue. The validation below uses the official flood
vector layer, not the source GeoTIFF.

The two NISAR HDF5 files were downloaded to `data/` (ignored by Git) with an
Earthdata token, opened correctly with `h5py` and were read over the study
area. `pipeline/make_db.py` produced the 40 m rasters and the detection was
repeated in a separate folder, without overwriting `outputs/`.

## Other sources searched

- **OPERA DSWx-S1:** the NASA CMR catalogue has 30 m granules of the
  `OPERA_L3_DSWX-S1_V1` collection over tiles that intersect the region,
  including acquisitions on 4 Jan and 16–17 Jan 2026. It is a Sentinel-1 water
  mapping collection with a stated revisit of 6–12 days. It was considered but
  not chosen, because EMSR857 offers emergency flood mapping over the AOI on
  the event date, which is more directly comparable.
- **OPERA DSWx-HLS:** the CMR query also returned granules in the region and
  period. It was not selected for the main reference validation.
- **UNOSAT:** the official catalogue returned product 4229, over Sofala, with
  an image of 5 Jan 2026, and products 4230–4232, for Gaza/Maputo, with images
  of 23–24 Jan 2026. The Gaza/Maputo products are geographically relevant but
  later than the NISAR scene of 17 Jan; 4229 covers another area.
- **Copernicus EMS:** the catalogue search found the flood activation EMSR857
  (Mozambique and South Africa), opened on 17 Jan 2026, with 17 AOIs and 43
  products. The AOI02 FEP item above was selected.

## Comparison and limits

A spatial comparison was made between the NISAR mask of new detectable open
water, reprocessed from the original HDF5 files, and the AOI02 `observedEventA`
vector layer:

| Measure in AOI02 | Result |
|---|---:|
| NISAR area of new detectable open water | 66.798 km² |
| EMS observed flood area | 93.048 km² |
| Intersection | 50.483 km² |
| Union | 109.364 km² |
| Intersection over Union (IoU) | 0.4616 |
| Intersection / NISAR area | 0.7557 |
| Intersection / EMS area | 0.5425 |

Method: the 811 features of the layer with `event_type = 5-Flood` were
selected (all also classed as `Riverine flood` and `Flooded area`); both layers
were cropped to the official AOI02 polygon and projected to UTM 36S
(EPSG:32736) to compute areas and the intersection. The AOI02 boundary is
labelled in the package as "First Estimate Product". The run
`detect_flood.py --loosen 3` reproduced exactly the published contract:
982.5 km² of change in detectable open water with `--loosen 3`, sensitivity
scenarios of 709.5–1,455.6 km² and 972.0 km² of permanent water. The strict
run without `--loosen` gives 709.5 km² and was not used in this comparison.

**Interpretation:** the numbers measure geometric agreement between these two
vectors, not scientific accuracy. The EMS product is a semi-automatic flood
extraction, not ground truth. The NISAR mask represents the change in
"detectable open water" relative to 5 January, while the EMS layer maps
flooded area; differences in class, coverage and method mean commission and
omission cannot be treated as absolute errors. The result is a reproducible
quantitative comparison with the product's official vector. The source
GeoTIFF was not in the package, so an independent visual inspection of the
Sentinel-1 image was not possible.

## Primary sources consulted

- [Copernicus EMS: EMSR857 activation page](https://mapping.emergency.copernicus.eu/activations/EMSR857/)
- [Copernicus EMS: activation API and product/AOI metadata](https://mapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR857)
- [NASA CMR: OPERA DSWx-S1 collection](https://cmr.earthdata.nasa.gov/search/collections.json?keyword=OPERA%20DSWx-S1&page_size=20)
- [NASA CMR: DSWx-S1 granules for January 2026 over the area](https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C2949811996-POCLOUD&temporal=2026-01-01T00%3A00%3A00Z%2C2026-02-01T00%3A00%3A00Z&bounding_box=31.98%2C-26.01%2C33.51%2C-23.99&page_size=100)
- [NASA CMR: OPERA DSWx-HLS collection](https://cmr.earthdata.nasa.gov/search/collections.json?keyword=OPERA%20DSWx-HLS&page_size=20)
- [UNOSAT: product 4229 metadata (Sofala, 5 Jan 2026)](https://unosat.org/our_products/4229)
- [UNOSAT: product 4231 metadata (Gaza/Maputo, 23–24 Jan 2026)](https://unosat.org/our_products/4231)

## Reproducing it and where it appears in the app

The comparison is reproducible in the repository:

```bash
python pipeline/validate_reference.py
```

The command needs `outputs/stats.json` with `mock: false`, the mask
`outputs/flood_extent.geojson` and the local package
`data/reference/EMSR857_products.zip`. It selects `event_type = 5-Flood`,
crops both layers to AOI02, computes the areas in EPSG:32736 and writes the
optional `validation` object to `outputs/stats.json`, plus
`outputs/validation_difference.geojson`. One invalid geometry in the NISAR
mask was repaired with `make_valid`; the number of repairs is recorded in the
contract (`geometry_repairs: 1`).

The interface shows these measures on story screen 3 ("Checked against an
independent map"), with the difference polygons on the map and the warning
that this is spatial agreement between different products, not ground truth.
The difference polygons are also a layer in the route tool. After changing the
results, run the validator before `pipeline/build_static.py` to update the
copy in `docs/`.
