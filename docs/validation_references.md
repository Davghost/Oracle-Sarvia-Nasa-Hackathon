# Validation reference candidates (T41) and notes (T33, T38)

Found by web search on 2026-11-14. These come from catalog summaries. **Nobody opened the actual files yet.** Check area, date and format before choosing one.

## T41: independent flood maps for Mozambique, January 2026

All are based on Sentinel-1 (C-band radar) or Copernicus products, so they are independent of NISAR (L-band). Good for the "Validity" criterion.

| Candidate | What it is | Why it may fit | What to check |
|---|---|---|---|
| [Copernicus EMS EMSR857](https://mapping.emergency.copernicus.eu/news/flood-in-mozambique-emsr857/) | Rapid Mapping activated on 17 Jan 2026 for the Mozambique flood. Maps cover the Xai-Xai area (as of 25 Jan, per the search summary) | Activated on the same date as our "during" scene (17/01) | Does it cover Chokwe/Macia? Are vectors (shapefile/GeoJSON) downloadable? |
| UNOSAT Sentinel-1 flood extent, 23-24 Jan 2026 (Gaza, Maputo provinces), on the Humanitarian Data Exchange | Automated analysis of Sentinel-1 | Provinces are the right region | Date is 6-7 days after our scene; flood extent may have changed |
| UNOSAT Sentinel-1 flood extent, 5 Jan 2026 | Same method | Same date as our "before" scene | **Sofala province, not our area.** Probably not useful |
| [CIMA Foundation update](https://www.cimafoundation.org/en/news/mozambique-heavy-rainfall-in-the-south-cooperation-and-monitoring-to-manage-flood-risk/) | Sentinel-1 flooded areas in the Incomati basin (29 Jan update) | Incomati is one of our two basins | Date is late; may be only a PDF map |
| [ECDM 2026-01-13 Mozambique (GDACS)](https://www.gdacs.org/contentdata/maps/daily/FL/1103694/ECDM_20260113_Mozambique.pdf) | Maximum flood extent 24 Dec 2025 to 13 Jan 2026 (Copernicus GloFAS/GFM, per summary) | Covers the period around both scenes | A PDF map only; hard to compare numerically |

Other context pages found: [Copernicus global flood news](https://global-flood.emergency.copernicus.eu/news/231-flooding-in-mozambique-december-2025-to-february-2026/), [JBA Risk summary](https://www.jbarisk.com/knowledge-hub/event-response/floods-in-southern-africa-january-2026/).

No OPERA DSWx product for this event was found.

**Suggested choice (not decided):** try EMSR857 first (same date). If vectors are not downloadable or the area does not match, use UNOSAT 23-24 Jan and say the 6-day gap in the app. Whatever we pick, say honestly that agreement is approximate.

## T33: submission and judging guides

The official 2026 pages could not be opened from this environment. A web search confirms (secondary summary, not the page itself):
- Demo: video up to 30 s or slide deck up to 7 slides (title included), hosted outside the Space Apps site, with a public link.
- If using slides, include team name, member names, the chosen challenge, and how space agency open data and technology made the project possible.
- English is required on the submission page and linked materials. A video in another language needs English subtitles.
- No source listing what changed from 2025 to 2026 was found. **Someone must read the official guide on their own computer** and note any change.

## T38: other dates on track 114, frame 165

Could not query ASF from here. Only confirmed from the file names we already have:
- GUNW `...008_114_A_165_009...20251224...20260105` implies an acquisition on 2025-12-24 (cycle 008).
- Whether a **GCOV** exists for 2025-12-24 is unknown. Check in ASF Vertex: dataset NISAR, track/path 114, frame 165, dates 2025-11-25 to 2026-01-31, product GCOV.

## Useful for T37 (HDF5 structure)

- NISAR L2 GCOV product specification (defines the HDF5 groups and datasets): [spec PDF](https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/DOCS/NISAR_D-102274_RevD_NASA_SDS_Product_Specification_L2_GCOV_w-sigs.pdf). Read it before writing the reader, and confirm with the real file using `h5ls -r`.
- Collection pages: [GCOV BETA V1](https://earthdata.nasa.gov/data/catalog/asf-nisar-l2-gcov-beta-v1-1) and [GCOV PROVISIONAL V1](https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gcov-provisional-v1-1). A BETA GCOV collection exists, which is probably where the January 2026 scenes live. Confirm the short name in ASF Vertex.
