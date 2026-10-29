# What the paper must say about the data

A checklist for the data parts of the paper (methods, data section, limitations, references, data availability). It lists what to include, the exact numbers, where each number comes from, and whether it can be cited yet. It does not write the paper: the wording and the reasoning are yours.

Status markers used below:

- **OK**: verified in this repo or in a document that was opened; cite as given.
- **VERIFY**: written from memory or from a page that could not be opened here; check it before citing.
- **NEEDS URL**: the document was read, but its URL or page was not recorded; record them first.
- **DON'T**: do not cite or claim this.

Where the numbers come from: `data/chalakudy/data_summary.json` (made by `python3 experiments/chalakudy.py summary`), `data/chalakudy/PROVENANCE.md` (every scenario parameter, labelled MEASURED, DERIVED or ASSUMED), `results/analysis_chalakudy/` (results) and `data/sources.md` (event dates). If a number here and one of those files ever disagree, the file wins.

## 1. Which data the paper uses

The paper has two flood experiments, and the data behind them is very different. Keep them apart in the text.

| | Kerala-anchored experiment (`kerala`, `kerala100`) | Chalakudy experiment (`chalakudy` and its sweeps) |
|---|---|---|
| Node positions | Synthetic: random in a 500 m square | Real: centroids of mapped buildings in a 1 km square of Chalakudy town |
| Which nodes fail | Synthetic terrain (ground rises eastward from a river, plus noise); lowest first | Real ground height (Copernicus DEM); lowest first |
| How many fail | 27% (press-reported statewide tower outage, used as a floor) or 50% (hypothetical) | 25% assumed; 10% and 50% swept |
| When | Dated 2018 events, compressed (1 day = 30 s) | Same dates and compression |
| Batteries | Assumed lifetimes (until 19 Aug – 6 Sep) | Assumed phone-sized battery and NS-3 radio currents |

Both are hypothetical scenarios anchored to real data. Neither is a measurement of how a mesh network behaved in Kerala in 2018, and the paper must not present them that way.

## 2. Data sources to cite (reference list)

| What | Cite | Licence / attribution you must include | Status |
|---|---|---|---|
| Municipality boundary | DataMeet, *Indian Village Boundaries*, Kerala file (`kl.geojson`), feature "Chalakudy", Town, Thrissur district, census 2001 code 3207000540727000. github.com/datameet/indian_village_boundaries (copy used: github.com/naveenpf/indian_village_boundaries), accessed 29 Oct 2026 | ODbL 1.0 | OK |
| Building footprints | Overture Maps Foundation, release 2026-10-21.0, buildings theme, accessed 29 Oct 2026. Their requested citation: "Overture Maps Foundation, overturemaps.org" | Overture distributes under ODbL; credit "© OpenStreetMap contributors, Overture Maps Foundation" | OK |
| ... of which Google Open Buildings | Sirko, W. et al. (2021), "Continental-scale building detection from high resolution satellite imagery", arXiv:2107.12283. Overture dates these records 2023-05-01 (Open Buildings v3) | Google states CC BY 4.0 and ODbL 1.0; the Overture records carry no licence field | VERIFY (citation from memory; licence page not opened here) |
| ... and OpenStreetMap | OpenStreetMap contributors, via Overture | ODbL 1.0; "© OpenStreetMap contributors" | OK |
| Rivers, canals, ponds | OpenStreetMap contributors, via Overture release 2026-10-21.0 (base theme, water) | ODbL 1.0 | OK |
| Ground height | Copernicus DEM GLO-30, tile N10E076, from the AWS Open Data copy (copernicus-dem-30m), accessed 29 Oct 2026. Usual citation: ESA (2021), Copernicus DEM, https://doi.org/10.5270/ESA-c5d3d65 | Copernicus DEM licence (GLO-30 public, free); attribution text required by the licence: "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" | VERIFY (DOI and exact attribution wording from memory; the licence page was blocked) |
| Radar images | Copernicus Sentinel-1 IW GRDH, 24 scenes (list in section 4.4 and `data/chalakudy/sentinel1_scenes.csv`), from the AWS archive `sentinel-s1-l1c`, accessed 29 Oct 2026 | Free, full and open (Sentinel Data Legal Notice). Put "Contains modified Copernicus Sentinel data [2018]" in the figure credits and acknowledgements | OK |
| Heavy rain 15–17 Aug | Government of Kerala, *Additional Memorandum*, 13 Sep 2018, Table 3, pp. 11–12 | cited only | OK |
| Dam releases 14–18 Aug; communication failure in Chalakudy taluk | Comptroller and Auditor General of India, Report No. 6 of 2021 (Kerala floods), Chapter III and §3.5.2. Use it for dated events only, not as a river level or flood curve | cited only | OK |
| Power restored (last Thrissur substation, 27 Aug) | KSEB, "How KSEBL survived flood 2018" | cited only | NEEDS URL (and which area the 27 Aug date covers) |
| Chalakudy flooded on 15 Aug / 17 Aug | Deccan Herald (early 15 Aug); Scroll, quoting an MP (17 Aug) | cited only | NEEDS URL (both articles) |
| Simulator | ns-3, version 3.47, https://www.nsnam.org | GPL-2.0 | OK |
| Path-loss model (sensitivity run) | 3GPP TR 37.885, *Study on evaluation methodology of new V2X use cases for LTE and NR*, V15.3.0 (2019-06), Table 6.2.1-1 (V2V Urban, NLOS), as implemented in ns-3.47 | cited only | VERIFY (version from the ns-3 documentation; the 3GPP document itself was not opened) |
| Water threshold method | Otsu, N. (1979), "A threshold selection method from gray-level histograms", *IEEE Trans. Systems, Man, and Cybernetics* 9(1): 62–66 | | VERIFY (from memory) |
| Statistics | Friedman, M. (1937), *J. American Statistical Association* 32(200): 675–701; Wilcoxon, F. (1945), *Biometrics Bulletin* 1(6): 80–83; Holm, S. (1979), *Scandinavian J. Statistics* 6(2): 65–70 | | VERIFY (from memory) |

Optional, if you compare your flood map with published ones: Tiwari et al. (2020), *PLoS ONE* 15(8): e0237324 (Sentinel-1 flood mapping of Kerala 2018). It could not be opened here (`MANUAL_DOWNLOADS.md` item 6), so read it before citing anything from it.

## 3. Say what is real, derived and assumed

Every number in the Chalakudy scenario is labelled in `data/chalakudy/PROVENANCE.md` (43 parameters, 13 sources). The paper needs a version of that table, at least in an appendix, plus one sentence in the methods saying that every input is labelled MEASURED (from a cited source), DERIVED (computed from measured data by a script in the repository) or ASSUMED (a choice, with its reason and, where it could matter, a sweep).

The short version for the methods section:

- **Measured:** municipality boundary; position and footprint of every mapped building; ground height (a surface model); rivers and ponds; open water on 24 radar images, January–September 2018; the dates of heavy rain, dam releases, Chalakudy's flooding and power restoration.
- **Derived:** the study square; each building's ground estimate; flood-water maps; each building's distance to radar-visible flood water; the order in which devices fail; network structure.
- **Assumed:** how many devices take part and in which buildings; how many buildings flood at the peak (25%; 10% and 50% swept); that water rises steadily from the onset to 18 Aug; that flooded devices do not come back; when the power was cut (the onset day); battery size and charge; the radio's energy use (ns-3 defaults); message traffic; the 150 m radio range; 1 day = 30 simulated seconds.

## 4. The data description, with the numbers

All numbers are from `data/chalakudy/data_summary.json` unless another file is named.

### 4.1 Study area

- Chalakudy municipality, Thrissur district, Kerala: 24.83 km² (from the DataMeet polygon), on the Chalakudy River (the municipality's southern edge follows it).
- 21,355 mapped buildings with their centroid inside the municipality: 11,841 from Google Open Buildings and 9,514 from OpenStreetMap; about 860 per km². Median footprint 101 m² (interquartile range 46–166 m²).
- Study square: 1 km × 1 km, south-west corner at UTM zone 43N (645297.5 E, 1138394.9 N). Rule (ASSUMED): of all 1 km squares at least 99% inside the municipality, the one holding the most buildings among the town's lowest 25% by ground estimate. Reason: ward-level flood records do not exist, so the lowest-lying built-up area stands in for the worst-hit wards.
- 1,383 buildings in the square (712 Google Open Buildings, 671 OpenStreetMap); 869 of them are among the town's lowest 25%.
- An alternative rule (most buildings within 300 m of radar-visible flood water on 21 Aug) picks a square with 838 buildings. It was recorded but not used; mention it if a reviewer could ask why this square.
- Figure: `results/analysis_chalakudy/figures/chalakudy_study_area` (buildings, devices of seed 1, which ones fail, radar water).

### 4.2 Devices (mesh nodes)

- 100 devices per run, each at the centroid of a different building drawn uniformly at random from the 1,383 (ASSUMED: there is no data on which households would run a mesh app). Seeds 1–10 give 10 different draws; for a given seed every protocol and scenario uses the same devices.
- Call them "mesh nodes" or "mobile devices", not phones (stock phones can't do ad-hoc routing).
- Density: 100 per km². That equals the density of the 25-node main grid (25 nodes in a 500 m square), not the 100-node one.
- Network at 150 m: mean degree 7.2 (main grid at the same density: 5.2); the largest connected group holds 96.7% of devices on average (main grid: 100%, by construction).
- Placement sensitivity (network structure only): drawing buildings in proportion to footprint area changes the mean degree by under 5% and the largest connected group from 97% to 94% (`network_structure.csv`).
- Figure: `chalakudy_network_density` (devices per km² against neighbours and connectivity, at 150 m and 62.8 m, with the main grid for comparison).

### 4.3 Ground height

- Copernicus DEM GLO-30. It is a surface model: heights include trees and roofs, not bare ground. Heights are relative to the EGM2008 geoid.
- Ground estimate per building (DERIVED): the 5th percentile of DEM cells within 50 m of the centroid (the lowest nearby cell is the best ground proxy a surface model gives).
- Municipality: median 15.0 m (10th–90th percentile 10.6–27.6 m). Study square: median 12.1 m (10th–90th percentile 10.0–13.5 m). The square is nearly flat.
- Used only to rank buildings from lowest to highest, never for absolute water levels: canopy bias makes absolute heights unreliable (the radar-visible flood water on 21 Aug sits at about 4.7 m on this DEM, while building ground estimates are around 12 m).

### 4.4 Radar flood maps

- 24 Sentinel-1 IW GRDH scenes, VV polarisation, 5 Jan – 26 Sep 2018: 22 from Sentinel-1A and 2 from Sentinel-1B; 22 descending passes (relative orbit 165, 00:40 UTC) and 2 ascending (orbit 173, about 13:06 UTC, on 21 and 27 Aug).
- **No image exists between 9 and 21 Aug, so the flood peak (15–18 Aug) was never observed.** The 21 Aug image shows only water still standing three days after the peak.
- Processing (`experiments/chalakudy_flood.py`), to describe in the methods:
  1. Calibration to backscatter (sigma0) with the product's calibration and thermal-noise tables.
  2. 5 × 5 boxcar speckle filter (ASSUMED).
  3. Placement on a 10 m grid (UTM 43N, municipality plus 1 km margin) from the product's geolocation grid, corrected for terrain height with the DEM. The geoid offset needed for that correction was estimated from the data (−96 m, the value that makes mapped rivers and ponds darkest against their surroundings, averaged over 6 descending scenes) because the geoid grid could not be downloaded. Afterwards checked against EGM2008 at the town centre: −95.7 m.
  4. Water threshold per scene: Otsu's method on a balanced sample of reference water cells and an equal number of land cells at least 150 m from mapped water. Thresholds −12.9 to −10.6 dB.
  5. Flood water = water on the date that was not water in at least half of the January–May scenes (permanent water) nor on 28 Jul (pre-event), in patches of at least 10 cells (0.1 ha).
- Quality checks to report: interior of mapped rivers and ponds detected as water in 68–93% of cells per scene; land at least 150 m from mapped water classified as water in 0.3–4.5% of cells (in dry-season scenes this bounds false detections; on 16 Jul, 9 Aug and 21 Aug part of it may be real flooding). The river on the radar maps follows the municipality's southern boundary (figure `chalakudy_qa_geolocation`, appendix).
- Flood water inside the municipality: 0.98 km² on 9 Aug, 0.98 km² on 21 Aug (descending) and 0.84 km² (ascending), 0.25 km² on 27 Aug; permanent water 0.39 km².
- **The key limitation:** radar cannot see water among buildings and trees (walls and trunks scatter the signal back, so flooded built-up areas look dry). In the study square no building lies within 20 m (or 50 m) of radar-visible flood water on any date; the nearest is 132 m on 21 Aug (descending), 58 m (ascending), 40 m on 9 Aug and 81 m on 27 Aug. So the radar shows that the fields around this part of town flooded and when the water receded, but it cannot say which buildings flooded.
- Full scene table for an appendix:

| Date (2018) | Time (UTC) | Satellite | Pass, orbit | Threshold (dB) | Water in grid (%) | Reference water detected (%) | Far land as water (%) |
|---|---|---|---|---|---|---|---|
| 5 Jan | 00:40 | S1A | descending 165 | −12.6 | 2.0 | 84.2 | 0.77 |
| 17 Jan | 00:40 | S1A | descending 165 | −12.7 | 1.8 | 82.2 | 0.55 |
| 29 Jan | 00:40 | S1A | descending 165 | −12.5 | 1.9 | 82.1 | 0.74 |
| 10 Feb | 00:40 | S1A | descending 165 | −12.8 | 2.0 | 82.0 | 0.72 |
| 22 Feb | 00:40 | S1A | descending 165 | −12.6 | 2.4 | 83.1 | 1.16 |
| 6 Mar | 00:40 | S1A | descending 165 | −12.5 | 2.6 | 82.9 | 1.41 |
| 18 Mar | 00:40 | S1A | descending 165 | −12.6 | 2.8 | 83.5 | 1.42 |
| 30 Mar | 00:40 | S1A | descending 165 | −12.6 | 2.5 | 82.8 | 1.32 |
| 11 Apr | 00:40 | S1A | descending 165 | −12.6 | 2.1 | 82.5 | 1.13 |
| 23 Apr | 00:40 | S1A | descending 165 | −12.4 | 2.0 | 83.9 | 0.77 |
| 5 May | 00:40 | S1A | descending 165 | −12.4 | 1.8 | 82.9 | 0.60 |
| 17 May | 00:40 | S1A | descending 165 | −12.2 | 2.0 | 83.5 | 0.72 |
| 29 May | 00:40 | S1A | descending 165 | −11.7 | 1.8 | 84.7 | 0.33 |
| 4 Jul | 00:40 | S1A | descending 165 | −11.8 | 1.9 | 85.8 | 0.43 |
| 16 Jul | 00:40 | S1A | descending 165 | −10.6 | 6.3 | 92.6 | 4.46 |
| 28 Jul | 00:40 | S1A | descending 165 | −12.4 | 1.9 | 87.5 | 0.50 |
| 9 Aug | 00:40 | S1A | descending 165 | −12.4 | 5.0 | 90.2 | 3.42 |
| 21 Aug | 00:40 | S1A | descending 165 | −12.2 | 5.0 | 91.0 | 3.19 |
| 21 Aug | 13:06 | S1A | ascending 173 | −12.9 | 4.2 | 85.1 | 2.56 |
| 27 Aug | 00:40 | S1B | descending 165 | −12.3 | 2.7 | 68.3 | 1.45 |
| 27 Aug | 13:05 | S1B | ascending 173 | −12.9 | 2.5 | 82.2 | 1.28 |
| 2 Sep | 00:40 | S1A | descending 165 | −12.4 | 2.6 | 90.6 | 1.34 |
| 14 Sep | 00:40 | S1A | descending 165 | −12.8 | 2.5 | 89.6 | 0.98 |
| 26 Sep | 00:40 | S1A | descending 165 | −12.8 | 2.2 | 89.8 | 0.69 |
