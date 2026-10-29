# Chalakudy experiment: work log

A running log of the `chalakudy` experiment, newest entry at the bottom. Times are commit times (UTC); entries written before 07:12 had estimated times and were corrected from `git log` on 29 Oct. It is committed and pushed to the `chalakudy-buildings` branch after every step, so work can resume from here if a session ends. The task itself is the owner's brief of 29 Oct 2026 (build a `chalakudy` experiment on real building locations and real 2018 data, with every number labelled measured, derived or assumed).

## Where things stand

| Step | State |
|---|---|
| Branch `chalakudy-buildings` from `overnight-experiments` (contains audit commits 9e9cd24a, b93ee861, 1c0a13cd) | done |
| Read CLAUDE.md, STATUS.md, DELIVERABLES-HANDOFF.md, experiments/README.md, docs/ns3-defaults.md, data/sources.md | done |
| Check which data hosts are reachable | done (see log 06:43) |
| Study area boundary | municipality polygon (DataMeet, ODbL); 1 km study square chosen by elevation rule (`study_area.json`) |
| Building footprints | done: Overture 2026-10-21.0, 21,355 in the municipality (11,841 Google Open Buildings 2023, 9,514 OSM) |
| Census (population, households) and device ownership | sources blocked; owner must download (list pending) |
| Elevation model | done: Copernicus GLO-30 tile N10E076 (surface model, includes trees/roofs) |
| River and channels | done: Overture base/water (OSM): Chalakudy River, canals, streams, ponds |
| 2018 flood extent | derived from Sentinel-1 (24 scenes); shows field flooding, cannot see water between buildings |
| Timeline, power restoration, cell towers, battery capacity | not started |
| `experiments/chalakudy.py` (raw data → simulator inputs) | in progress: building table, study square, network stats done |
| `data/chalakudy/PROVENANCE.md` | not started |
| Ask owner about predictions (before any run) | not started |
| Runs, checks, analysis, docs, report | not started |

## Log

### 2026-10-29 06:38 UTC

- Confirmed `origin/overnight-experiments` contains 9e9cd24a, b93ee861 and 1c0a13cd (first check found them missing; the owner pushed them, second check passed). Fast-forwarded and created `chalakudy-buildings` at 1c0a13c.
- Read the six files listed in the brief.
- NS-3.47 build and the `manet` binary are still present in this container; numpy, pandas, scipy, matplotlib and networkx are installed. GIS libraries (geopandas, shapely, rasterio, pyproj) are not installed yet.
- Next: install the GIS libraries, then test which data hosts the network policy allows (OpenStreetMap, building datasets, elevation models, flood maps, census).

### 2026-10-29 06:43 UTC: which data hosts are reachable

Tested on 29 Oct 2026 from this cloud session. "Blocked" = the session's network proxy refused the connection (`curl: (56) CONNECT tunnel failed, response 403`). Full list: `data/chalakudy/host_check.txt`.

Reachable (HTTP 200):
- `storage.googleapis.com`: Google Open Buildings v3 (`open-buildings-data`), Global Flood Database v1.4 (`gfd_v1_4`), Earth Engine public bucket.
- `overturemaps-us-west-2.s3.amazonaws.com`: Overture Maps (OSM-derived boundaries, water, buildings incl. Microsoft and Google footprints).
- `copernicus-dem-30m.s3.amazonaws.com`: Copernicus GLO-30 elevation model.
- `sentinel-s1-l1c.s3.amazonaws.com`: Sentinel-1 GRD archive (listing and anonymous download both work).
- `elevation-tiles-prod.s3.amazonaws.com`, `maxar-opendata.s3.amazonaws.com` (no Kerala 2018 event listed), `raw.githubusercontent.com`, `api.github.com`, `pypi.org`.

Blocked (403 at the proxy): openstreetmap.org (Overpass, Nominatim, API), download.geofabrik.de, data.humdata.org, Microsoft footprint blob (minedbuildings.z5.web.core.windows.net), prism-dem-open.copernicus.eu, srtm.csi.cgiar.org, opentopography.org, global-flood-database.cloudtostreet.ai, unosat.org, emergency.copernicus.eu, bhuvan.nrsc.gov.in, floodobservatory.colorado.edu, journals.plos.org, zenodo.org, figshare.com, censusindia.gov.in, data.gov.in, citypopulation.de, en.wikipedia.org, trai.gov.in, rchiips.org (NFHS), opencellid.org, geodata.ucdavis.edu (GADM), kseb.in, cag.gov.in, sdma.kerala.gov.in, lsgkerala.gov.in, planetarycomputer.microsoft.com, Azure blob storage, earth-search.aws.element84.com, dataspace.copernicus.eu, search.asf.alaska.edu, cmr.earthdata.nasa.gov.

### 2026-10-29 06:43 UTC: Global Flood Database has no Kerala 2018 event

- Read the metadata of every 2018 event in `gs://gfd_v1_4` that overlaps July–September (range requests on the zips; script `experiments/chalakudy_fetch.py`, to be added). The two Indian events are DFO 4665 (2–10 Aug, centroid 27.3°N 94.1°E, north-east India/Bangladesh) and DFO 4673 (1–7 Sep, centroid 25.7°N 82.4°E). Neither covers Kerala, so Kerala's August 2018 flood is not in the database. A likely reason (not verified) is that it is built from MODIS optical imagery, which monsoon cloud blocks.
- Downloaded DFO 4662 by mistake while checking (South America); it is not used.
- Licence of the database: CC BY-NC 4.0 (from the LICENSE.txt in each zip).

### 2026-10-29 06:43 UTC: Sentinel-1 radar is downloadable

- `sentinel-s1-l1c` on AWS serves 2018 IW GRD scenes anonymously. Each scene has a `productInfo.json` with its footprint; the VV image is about 700 MB.
- Plan: find every scene covering Chalakudy from July to September 2018, then map open water by thresholding radar backscatter (a standard change-detection method; method and threshold to be cited), giving a measured-from-satellite flood extent on the actual overpass dates.
- Raw downloads go to `data/chalakudy/raw/` (git-ignored); checksums and re-download instructions will be committed.

### 2026-10-29 06:49 UTC: Sentinel-1 scenes over Chalakudy, July–September 2018

- `experiments/chalakudy_fetch.py s1-scan 2018-07-01 2018-09-30`: listed 7,838 IW scenes acquired at Kerala overpass times, read each footprint, kept those that fully cover a box around Chalakudy town (76.25–76.40°E, 10.25–10.36°N). Result: `data/chalakudy/sentinel1_scenes.csv`, 11 scenes:
  - descending, relative orbit 165 (about 00:40 UTC = 06:10 IST): 4, 16, 28 Jul; 9, 21 Aug; 2, 14, 26 Sep (Sentinel-1A, 12-day repeat) and 27 Aug (Sentinel-1B);
  - ascending, relative orbit 173 (about 13:06 UTC = 18:36 IST): 21 and 27 Aug.
- No scene between 10 and 20 Aug, so the flood peak (15–17 Aug) was not imaged. The 21 Aug 06:10 IST scene is the first after the peak; it can only show water that was still standing then, so it is a lower bound on the peak extent.
- First scan attempt failed with `ConnectionResetError` from the proxy; added retries and fewer parallel requests.

### 2026-10-29 06:53 UTC: boundary found; census sources blocked

- Overture's `division_area` near Chalakudy (fetched with `chalakudy_fetch.py overture divisions division_area`, reading only matching Parquet row groups because Overture's STAC catalog host is blocked) has Kerala, Thrissur district and a few small localities, but no Chalakudy municipality or ward polygons.
- GitHub search API is not available to this session (only repo-scoped endpoints). raw.githubusercontent.com works, so known files can be fetched.
- Boundary: `naveenpf/indian_village_boundaries` (mirror of DataMeet's Indian Village Boundaries, ODbL), file `kl/kl.geojson`, has "Chalakudy", TYPE Town, census 2001 code 3207000540727000, Mukundapuram sub-district, Thrissur. Its notes (`kl/kl.md`) give the source as the Kerala LSG "Delimitation Map 2010, Maps of Villages and Towns" (delimitation.lsgkerala.gov.in/map). Polygon area 24.83 km² (UTM 43N), 5.4 km × 7.7 km, centroid 76.3278°E 10.3126°N.
- Census figures appear only in search-result snippets (population 49,525 in 2011; households 12,567 per a Kudumbashree page vs 12,218 per the AMRUT city water balance plan; area 25.23 km²; 36 wards). These are NOT verified: kudumbashree.org, amrutkerala.org, censusindia.gov.in, wikipedia and citypopulation.de are all blocked, and the WebFetch tool is blocked for the same hosts (`getaddrinfo ENOTFOUND`). They will need manual download by the owner.
- Ward boundaries: not available (OSM blocked; no ward file in the DataMeet repo).

Design problem found: at the 150 m unit-disk range the whole 24.8 km² municipality would need roughly 2,800 nodes for a connected mesh (about 8 neighbours per node), far beyond what NS-3 can run here (100-node runs take minutes each and AODV collapses there). So the simulated area has to be a smaller part of the town, chosen from data (where buildings and measured 2018 flooding coincide), with the number of nodes set by device density × a swept participation rate. To be decided after the flood map is made.

### 2026-10-29 06:57 UTC: buildings, rivers, elevation; flood-map route

- Buildings (`chalakudy_fetch.py overture buildings building 76.29 10.26 76.37 10.36`): 65,958 footprints in the box, 21,355 with centroid inside the municipality: 11,841 from Google Open Buildings (Overture says update year 2023) and 9,514 from OpenStreetMap (6,850 last edited in 2018). Footprints are later than or close to 2018, so some buildings may not have existed in Aug 2018 (limitation).
- Water (`... overture base water`): 3,604 features incl. "Chalakudy River"/"Chalakkudy" river polygons, irrigation canals (Idamalayar, Chalakudy), streams, 1,375 ponds.
- Elevation: Copernicus GLO-30 DSM tile `Copernicus_DSM_COG_10_N10_00_E076_00_DEM.tif` from copernicus-dem-30m.s3.amazonaws.com (45.9 MB, checksum in downloads.csv). 1 arc-second (~30 m), heights relative to the EGM2008 geoid, surface model (includes trees and roofs).
- Ready-made 2018 flood maps: none reachable. The Dartmouth Flood Observatory page for event 4663 (https://floodobservatory.colorado.edu/Events/4663/2018India4663.html) reportedly lists Sentinel-1 flood-extent shapefiles, but the host is blocked. Owner to download if possible (cross-check).
- Sentinel-1 GRD images can be read remotely by window (GDAL /vsicurl/, tiles 1024×1024), so only the Chalakudy part of each 700 MB image is fetched.
- Geolocation problem found: GRD geolocation grids use a reference height per image line (255–402 m on 21 Aug), while Chalakudy's ground is near sea level and the geoid around Kerala is well below the ellipsoid. Without correction, pixels would be displaced by hundreds of metres in range. The geoid model (cdn.proj.org, download.osgeo.org) is blocked, so the constant geoid offset will be estimated from the data by aligning the Chalakudy River's dark water pixels with the OSM river polygon; the DEM handles height differences inside the area.

### 2026-10-29 07:12 UTC: flood maps from Sentinel-1 (`experiments/chalakudy_flood.py`)

What the script does: reads only the Chalakudy window of each VV image; calibrates to sigma0 with the image's calibration and thermal-noise tables (2018 products use the older `noiseVector`/`noiseLut` layout; the script handles both); 5×5 moving average against speckle; puts every pixel on a 10 m UTM 43N grid with a terrain correction; classifies water with Otsu's threshold.

Results (`data/chalakudy/flood/scenes_processed.csv`, `geoid_offset_scan.csv`, `water_*.tif`):
- Geolocation: GRD images are placed on a reference surface 255–720 m high (per image line); Chalakudy's ground is near sea level. The geoid offset that lines dark radar pixels up with mapped water (OSM river and ponds ≥ 2,000 m²) is −96 m in 5 of 6 calibration scenes (−92 m in one), with mapped water 7.4 dB darker than its surroundings. Polynomial fit of the image geometry: max residual 0.03 pixel at the grid points.
- Threshold: Otsu on the whole-area histogram failed (in March it picked −8.3 dB and called 37% of the area water) because water is only a few per cent of cells. Fixed by computing Otsu per image on a balanced sample: all mapped-water cells plus an equal random sample of land ≥150 m from mapped water. Thresholds then lie between −10.6 and −12.95 dB (mostly about −12.5 dB); 82–93% of mapped water cells and under 1% of far land are classed as water in the dry season.
- Open water in the grid (municipality + 1 km margin): about 2% in Jan–May; 6.3% on 16 Jul; 1.9% on 28 Jul; 5.0% on 9 Aug; 5.0% on 21 Aug 06:10 IST; 4.2% on 21 Aug 18:36 IST; ~2.6% on 27 Aug and 2 Sep.
- New flood water inside the municipality (water that was not water on 28 Jul and is not permanent, i.e. not water in ≥ half the dry-season images): 1.01 km² (4.1% of the area) on 9 Aug and on 21 Aug morning, 0.86 km² on 21 Aug evening, 0.26 km² on 27 Aug, 0.20 km² on 2 Sep. The water was receding after the (unimaged) peak.
- QA map: `data/chalakudy/figures/qa_flood_2018-08-21.png`. The Chalakudy River lines up with the municipality's southern boundary (which follows the river), so the geolocation correction works.

Bug found and fixed (in an exploratory check, not in a committed script): counting buildings near flood water with `scipy.ndimage.minimum(..., labels=footprint_raster)` gave about 1,500 "flooded" buildings on every date. Cause: small adjoining footprints lose all their 10 m cells to neighbours when rasterised, and `ndimage.minimum` returns 0 for a label with no cells. Fixed by measuring distance at each footprint's own vertices and centroid.

Key finding: with the fix, only 8–31 of 21,355 buildings have radar-visible flood water within 10–20 m on 21 Aug (2–22 on 9 Aug; 3–31 on 27 Aug; numbers depend on a minimum flood-patch size of 1–25 cells). The radar sees flooded fields around the town but not water between houses: walls and trees scatter the signal back to the satellite, so flooded built-up areas do not look dark. Sentinel-1 therefore gives (a) a measured lower bound and (b) the recession timing, but it cannot say which buildings flooded at the 15–18 Aug peak. Building-level flooding will have to come from ground height (Copernicus DEM) with the peak water level as an assumed, swept parameter, anchored to the water level of the flood patches the radar does see on 21 Aug.

Documents the owner will need to download (sites blocked here): see `data/chalakudy/MANUAL_DOWNLOADS.md` (being written).

### 2026-10-29 07:20 UTC: elevation can rank buildings but not set absolute flood levels

- Copernicus DEM heights (EGM2008): municipality 5–34 m (5th–95th percentile, median 16 m); permanent water near the town 1–3 m; flood patches seen on 21 Aug: median 4.7 m, patch edges median 4.9 m (a consistent water-surface estimate for that morning); 9 Aug similar; 27 Aug patches higher and patchier.
- Buildings: surface height at the centroid median 17.2 m. A "local ground" estimate (5th percentile of the surface model within 50 m) has median 15.0 m, still ~10 m above the flooded fields. Most houses stand among coconut palms and other trees, and the DEM is a surface model, so even the lowest nearby cell is often canopy.
- Consequence: with this DEM, only 0.5% of buildings lie below the 21-Aug water surface, 4% below +4 m, 28% below +8 m. The absolute numbers are not trustworthy because of canopy bias. The DEM is used only to RANK buildings (lowest first). The share of buildings flooded at the peak is ASSUMED and swept. A bare-earth DEM (FABDEM, item 8 in MANUAL_DOWNLOADS.md) would improve the ranking.
- Next: `experiments/chalakudy.py` to choose a study area, sample nodes at building centroids, and build flood, battery and traffic schedules.

### 2026-10-29 07:30 UTC: building table, study square, real network structure

- `python3 experiments/chalakudy.py prepare` writes `data/chalakudy/buildings.csv` (21,355 buildings: Overture id, source, UTM centroid, footprint area, DSM at centroid, ground estimate, distance from footprint to Sentinel-1 flood water on 9, 21 (both passes) and 27 Aug) and `data/chalakudy/study_area.json`.
- Study square (rule: 1 km square ≥ 99% inside the municipality with the most buildings among the town's lowest 25% by ground estimate): SW corner x0 = 645297, y0 = 1138395 (UTM 43N), 1,383 buildings, 869 of them in the lowest 25%. Alternative rule (most buildings within 300 m of 21-Aug flood water) picks x0 = 643597, y0 = 1138845 with 838 buildings; recorded, not used.
- Network at 150 m range in the main square (10 random samples each): 50 devices: mean degree 3.5, largest connected part 51%, diameter ~9 hops; 100 devices: 7.3, 88%, ~14 hops; 150 devices: 10.8, 99%, ~12 hops. Main grid for comparison: mean degree 5.2/10.5/22.4 at 25/50/100 nodes, diameter 5–11. Real buildings cluster along roads, so routes are long; DSDV start-up needs checking before running (warm-up rule 7).
- Placement-rule sensitivity (network structure only): sampling buildings by footprint area instead of uniformly changes mean degree by under 2%; at 100 devices it raises the largest connected part from 88% to 98.5%.

### 2026-10-29 07:40 UTC: run generator written; one accidental start, stopped

- `chalakudy.py` now builds simulator inputs per (node count, seed): nodes sampled from the study square's buildings, flows within connected parts, flood schedule (observed-flooded first, then lowest ground), uniform-random baseline with the same failure times, no-flood control, batteries. Variants: `chalakudy` (main: onset 15 and 17 Aug × batteries limited/unlimited, 360 runs), `chalakudy_share` (120), `chalakudy_nodes` (180), `chalakudy_traffic` (180), `chalakudy_battery` (180).
- Mistake: a command meant as a quick check started the full onset-15 half of the main experiment in the background, before the owner had been asked about predictions or compute. Noticed within about a minute and stopped (`kill` on the run_experiment and simulator processes). No run finished: 4 half-written run folders, no summaries; they were moved out of the repo to the session scratchpad and nothing from them was looked at or committed.
- Next: a pilot of no-flood control runs only (seed 1; 100 and 150 nodes; batteries limited and unlimited), written to the scratch experiment `chalakudy_pilot`, used only for run time, routing-table start-up and error checks. No delivery results are looked at.
