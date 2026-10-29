# Chalakudy experiment: work log

A running log of the `chalakudy` experiment, newest entry at the bottom. It is committed and pushed to the `chalakudy-buildings` branch after every step, so work can resume from here if a session ends. The task itself is the owner's brief of 29 Oct 2026 (build a `chalakudy` experiment on real building locations and real 2018 data, with every number labelled measured, derived or assumed).

## Where things stand

| Step | State |
|---|---|
| Branch `chalakudy-buildings` from `overnight-experiments` (contains audit commits 9e9cd24a, b93ee861, 1c0a13cd) | done |
| Read CLAUDE.md, STATUS.md, DELIVERABLES-HANDOFF.md, experiments/README.md, docs/ns3-defaults.md, data/sources.md | done |
| Check which data hosts are reachable | done (see log 06:45) |
| Study area boundary | municipality polygon found (DataMeet/naveenpf, ODbL); sub-area choice pending |
| Building footprints | not started |
| Census (population, households) and device ownership | sources blocked; owner must download (list pending) |
| Elevation model | not started |
| River and channels | not started |
| 2018 flood extent | not started |
| Timeline, power restoration, cell towers, battery capacity | not started |
| `experiments/chalakudy.py` (raw data → simulator inputs) | not started |
| `data/chalakudy/PROVENANCE.md` | not started |
| Ask owner about predictions (before any run) | not started |
| Runs, checks, analysis, docs, report | not started |

## Log

### 2026-10-29 06:38 UTC

- Confirmed `origin/overnight-experiments` contains 9e9cd24a, b93ee861 and 1c0a13cd (first check found them missing; the owner pushed them, second check passed). Fast-forwarded and created `chalakudy-buildings` at 1c0a13c.
- Read the six files listed in the brief.
- NS-3.47 build and the `manet` binary are still present in this container; numpy, pandas, scipy, matplotlib and networkx are installed. GIS libraries (geopandas, shapely, rasterio, pyproj) are not installed yet.
- Next: install the GIS libraries, then test which data hosts the network policy allows (OpenStreetMap, building datasets, elevation models, flood maps, census).

### 2026-10-29 06:45 UTC: which data hosts are reachable

Tested on 29 Oct 2026 from this cloud session. "Blocked" = the session's network proxy refused the connection (`curl: (56) CONNECT tunnel failed, response 403`). Full list: `data/chalakudy/host_check.txt`.

Reachable (HTTP 200):
- `storage.googleapis.com`: Google Open Buildings v3 (`open-buildings-data`), Global Flood Database v1.4 (`gfd_v1_4`), Earth Engine public bucket.
- `overturemaps-us-west-2.s3.amazonaws.com`: Overture Maps (OSM-derived boundaries, water, buildings incl. Microsoft and Google footprints).
- `copernicus-dem-30m.s3.amazonaws.com`: Copernicus GLO-30 elevation model.
- `sentinel-s1-l1c.s3.amazonaws.com`: Sentinel-1 GRD archive (listing and anonymous download both work).
- `elevation-tiles-prod.s3.amazonaws.com`, `maxar-opendata.s3.amazonaws.com` (no Kerala 2018 event listed), `raw.githubusercontent.com`, `api.github.com`, `pypi.org`.

Blocked (403 at the proxy): openstreetmap.org (Overpass, Nominatim, API), download.geofabrik.de, data.humdata.org, Microsoft footprint blob (minedbuildings.z5.web.core.windows.net), prism-dem-open.copernicus.eu, srtm.csi.cgiar.org, opentopography.org, global-flood-database.cloudtostreet.ai, unosat.org, emergency.copernicus.eu, bhuvan.nrsc.gov.in, floodobservatory.colorado.edu, journals.plos.org, zenodo.org, figshare.com, censusindia.gov.in, data.gov.in, citypopulation.de, en.wikipedia.org, trai.gov.in, rchiips.org (NFHS), opencellid.org, geodata.ucdavis.edu (GADM), kseb.in, cag.gov.in, sdma.kerala.gov.in, lsgkerala.gov.in, planetarycomputer.microsoft.com, Azure blob storage, earth-search.aws.element84.com, dataspace.copernicus.eu, search.asf.alaska.edu, cmr.earthdata.nasa.gov.

### 2026-10-29 06:55 UTC: Global Flood Database has no Kerala 2018 event

- Read the metadata of every 2018 event in `gs://gfd_v1_4` that overlaps July–September (range requests on the zips; script `experiments/chalakudy_fetch.py`, to be added). The two Indian events are DFO 4665 (2–10 Aug, centroid 27.3°N 94.1°E, north-east India/Bangladesh) and DFO 4673 (1–7 Sep, centroid 25.7°N 82.4°E). Neither covers Kerala, so Kerala's August 2018 flood is not in the database. A likely reason (not verified) is that it is built from MODIS optical imagery, which monsoon cloud blocks.
- Downloaded DFO 4662 by mistake while checking (South America); it is not used.
- Licence of the database: CC BY-NC 4.0 (from the LICENSE.txt in each zip).

### 2026-10-29 07:00 UTC: Sentinel-1 radar is downloadable

- `sentinel-s1-l1c` on AWS serves 2018 IW GRD scenes anonymously. Each scene has a `productInfo.json` with its footprint; the VV image is about 700 MB.
- Plan: find every scene covering Chalakudy from July to September 2018, then map open water by thresholding radar backscatter (a standard change-detection method; method and threshold to be cited), giving a measured-from-satellite flood extent on the actual overpass dates.
- Raw downloads go to `data/chalakudy/raw/` (git-ignored); checksums and re-download instructions will be committed.

### 2026-10-29 07:20 UTC: Sentinel-1 scenes over Chalakudy, July–September 2018

- `experiments/chalakudy_fetch.py s1-scan 2018-07-01 2018-09-30`: listed 7,838 IW scenes acquired at Kerala overpass times, read each footprint, kept those that fully cover a box around Chalakudy town (76.25–76.40°E, 10.25–10.36°N). Result: `data/chalakudy/sentinel1_scenes.csv`, 11 scenes:
  - descending, relative orbit 165 (about 00:40 UTC = 06:10 IST): 4, 16, 28 Jul; 9, 21 Aug; 2, 14, 26 Sep (Sentinel-1A, 12-day repeat) and 27 Aug (Sentinel-1B);
  - ascending, relative orbit 173 (about 13:06 UTC = 18:36 IST): 21 and 27 Aug.
- No scene between 10 and 20 Aug, so the flood peak (15–17 Aug) was not imaged. The 21 Aug 06:10 IST scene is the first after the peak; it can only show water that was still standing then, so it is a lower bound on the peak extent.
- First scan attempt failed with `ConnectionResetError` from the proxy; added retries and fewer parallel requests.

### 2026-10-29 07:45 UTC: boundary found; census sources blocked

- Overture's `division_area` near Chalakudy (fetched with `chalakudy_fetch.py overture divisions division_area`, reading only matching Parquet row groups because Overture's STAC catalog host is blocked) has Kerala, Thrissur district and a few small localities, but no Chalakudy municipality or ward polygons.
- GitHub search API is not available to this session (only repo-scoped endpoints). raw.githubusercontent.com works, so known files can be fetched.
- Boundary: `naveenpf/indian_village_boundaries` (mirror of DataMeet's Indian Village Boundaries, ODbL), file `kl/kl.geojson`, has "Chalakudy", TYPE Town, census 2001 code 3207000540727000, Mukundapuram sub-district, Thrissur. Its notes (`kl/kl.md`) give the source as the Kerala LSG "Delimitation Map 2010, Maps of Villages and Towns" (delimitation.lsgkerala.gov.in/map). Polygon area 24.83 km² (UTM 43N), 5.4 km × 7.7 km, centroid 76.3278°E 10.3126°N.
- Census figures appear only in search-result snippets (population 49,525 in 2011; households 12,567 per a Kudumbashree page vs 12,218 per the AMRUT city water balance plan; area 25.23 km²; 36 wards). These are NOT verified: kudumbashree.org, amrutkerala.org, censusindia.gov.in, wikipedia and citypopulation.de are all blocked, and the WebFetch tool is blocked for the same hosts (`getaddrinfo ENOTFOUND`). They will need manual download by the owner.
- Ward boundaries: not available (OSM blocked; no ward file in the DataMeet repo).

Design problem found: at the 150 m unit-disk range the whole 24.8 km² municipality would need roughly 2,800 nodes for a connected mesh (about 8 neighbours per node), far beyond what NS-3 can run here (100-node runs take minutes each and AODV collapses there). So the simulated area has to be a smaller part of the town, chosen from data (where buildings and measured 2018 flooding coincide), with the number of nodes set by device density × a swept participation rate. To be decided after the flood map is made.
