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
