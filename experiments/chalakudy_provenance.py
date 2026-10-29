"""Writes data/chalakudy/PROVENANCE.md and data/chalakudy/derived_files.csv.

Every number in the Chalakudy scenario is in chalakudy.PARAMS with its value, kind (measured, derived or
assumed), reasoning and sweep. This script adds where each one came from (SOURCES, USES) and renders the
table, so the document cannot drift from the code. It also records the size and SHA-256 of every derived
data file, so a rerun of the pipeline can be checked against them.

    python3 experiments/chalakudy_provenance.py
"""

import csv
import glob
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chalakudy as C  # noqa: E402

DATA = C.DATA

# key: (title, URL, page or section, accessed, licence)
SOURCES = {
    "datameet": (
        "DataMeet, Indian Village Boundaries, Kerala file kl.geojson; feature NAME 'Chalakudy', TYPE Town, "
        "DISTRICT Thrissur, CEN_2001 3207000540727000",
        "https://raw.githubusercontent.com/naveenpf/indian_village_boundaries/master/kl/kl.geojson (copy of "
        "github.com/datameet/indian_village_boundaries)",
        "whole file; one feature used", "29 Oct 2026 06:52 UTC",
        "ODbL 1.0 (README and LICENSE of the repository, read 29 Oct 2026)"),
    "overture_buildings": (
        "Overture Maps Foundation, release 2026-10-21.0, theme buildings, type building",
        "https://overturemaps-us-west-2.s3.amazonaws.com/release/2026-10-21.0/theme=buildings/type=building/",
        "row groups overlapping lon 76.29-76.37, lat 10.26-10.36", "29 Oct 2026 06:54 UTC",
        "per-record licence field: OpenStreetMap records ODbL-1.0; Google Open Buildings records have an empty "
        "field (Google publishes Open Buildings under CC BY 4.0 and ODbL 1.0; not opened here, verify at "
        "sites.research.google/open-buildings). Cite 'Overture Maps Foundation, overturemaps.org' and "
        "'© OpenStreetMap contributors'"),
    "overture_water": (
        "Overture Maps Foundation, release 2026-10-21.0, theme base, type water (from OpenStreetMap)",
        "https://overturemaps-us-west-2.s3.amazonaws.com/release/2026-10-21.0/theme=base/type=water/",
        "row groups overlapping lon 76.2-76.45, lat 10.2-10.42", "29 Oct 2026 06:54 UTC",
        "ODbL-1.0 (per-record licence field)"),
    "copernicus_dem": (
        "Copernicus DEM GLO-30, tile Copernicus_DSM_COG_10_N10_00_E076_00_DEM (a surface model: includes "
        "trees and roofs; heights above the EGM2008 geoid)",
        "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N10_00_E076_00_DEM/"
        "Copernicus_DSM_COG_10_N10_00_E076_00_DEM.tif",
        "whole tile", "29 Oct 2026 06:55 UTC",
        "Copernicus DEM licence, GLO-30 Public: free for the general public (bucket readme and AWS Open Data "
        "registry entry, read 29 Oct 2026)"),
    "sentinel1": (
        "Copernicus Sentinel-1A and 1B IW GRDH, 24 scenes 5 Jan - 26 Sep 2018 (list: data/chalakudy/sentinel1_scenes.csv)",
        "https://sentinel-s1-l1c.s3.amazonaws.com/GRD/2018/ (annotation, calibration and noise XML downloaded, "
        "checksums in downloads.csv; the VV measurement GeoTIFFs were read over HTTP in windows around the "
        "town, not downloaded whole)",
        "VV band, window around the municipality", "29 Oct 2026 07:04-07:08 UTC (XML); image windows read "
        "29 Oct 2026",
        "Copernicus Sentinel data: free, full and open (Sentinel Data Legal Notice, via the AWS Open Data "
        "registry entry). Credit: 'Contains modified Copernicus Sentinel data 2018'"),
    "kseb": (
        "KSEB, 'How KSEBL survived flood 2018'", "kseb.in (exact URL not recorded; data/sources.md)",
        "restoration dates", "opened before 12 Oct 2026 (data/sources.md)", "copyrighted document, cited only"),
    "cag": (
        "CAG Report No. 6 of 2021 (Kerala floods)", "https://cag.gov.in/ag1/kerala/en/audit-report/details/114526",
        "Chapter III (dam releases 14-18 Aug); §3.5.2 (communications)", "opened before 12 Oct 2026 "
        "(data/sources.md)", "government report, cited only"),
    "memorandum": (
        "Government of Kerala, Additional Memorandum, 13 Sep 2018",
        "https://recovery.preventionweb.net/media/101476/download",
        "Table 3, p. 11 and p. 12 (IMD red rain 15-17 Aug)", "opened before 12 Oct 2026 (data/sources.md)",
        "government report, cited only"),
    "press_onset": (
        "Deccan Herald (Chalakudy flooded early 15 Aug) and Scroll quoting an MP (17 Aug)",
        "URLs not recorded in data/sources.md", "news reports", "opened before 12 Oct 2026 (data/sources.md)",
        "press, cited only; the two disagree"),
    "kerala_exp": (
        "This repository's kerala experiment (experiments/README.md section 5)", "experiments/kerala.py", "-", "-",
        "-"),
    "sources_missing": (
        "data/sources.md, 'Missing': message traffic during the disaster is not documented", "data/sources.md",
        "-", "-", "-"),
    "ns3": (
        "ns-3.47 source code", "https://www.nsnam.org/releases/ns-3-47/ (checked values: docs/ns3-defaults.md)",
        "files named in docs/ns3-defaults.md", "checked 27-29 Oct 2026", "GPL-2.0"),
    "3gpp": (
        "3GPP TR 37.885, 'Study on evaluation methodology of new V2X use cases for LTE and NR', Table 6.2.1-1 "
        "(V2V Urban, NLOS), as implemented in ns-3.47 src/propagation/model/three-gpp-v2v-propagation-loss-model.cc "
        "(GetLossNlos)", "https://www.3gpp.org/ftp/Specs/archive/37_series/37.885/ (blocked here; formula read "
        "from the ns-3 code, which cites the table)", "Table 6.2.1-1", "ns-3 code read 29 Oct 2026",
        "3GPP specification, cited only"),
}

# parameter: (source keys, where it is used)
USES = {
    "study_side_m": ([], "chalakudy.py prepare (choose_square) -> study_area.json"),
    "study_area_rule": (["datameet", "overture_buildings", "copernicus_dem"], "chalakudy.py prepare -> study_area.json"),
    "nodes": ([], "chalakudy.py VARIANTS"),
    "placement": (["overture_buildings"], "chalakudy.py sample_nodes"),
    "ground_estimate": (["copernicus_dem"], "chalakudy.py building_table -> buildings.csv"),
    "observed_flood_buffer_m": (["sentinel1"], "chalakudy.py flood_order"),
    "peak_flooded_share": ([], "chalakudy.py flood_events"),
    "onset_day": (["press_onset"], "chalakudy.py flood_events"),
    "peak_day": (["memorandum", "cag"], "chalakudy.py flood_events"),
    "flooded_nodes_return": (["sentinel1"], "chalakudy.py flood_events"),
    "power_cut_day": (["kseb"], "chalakudy.py battery_energy"),
    "power_back_day": (["kseb"], "chalakudy.py SIM_END_S"),
    "battery_capacity_mah": ([], "chalakudy.py battery_energy"),
    "battery_voltage_v": ([], "chalakudy.py battery_energy"),
    "radio_share_of_battery": ([], "chalakudy.py battery_energy"),
    "charge_at_power_cut": ([], "chalakudy.py battery_energy"),
    "radio_power_model": (["ns3"], "sim/manet/manet.cc; chalakudy.py IDLE_W"),
    "day_s": (["kerala_exp"], "chalakudy.py day()"),
    "flows": (["kerala_exp"], "chalakudy.py component_flows"),
    "burst_mean_gap_s": (["sources_missing"], "chalakudy.py component_flows"),
    "s1_scenes": (["sentinel1"], "chalakudy_fetch.py s1-scan -> sentinel1_scenes.csv"),
    "grid_cell_m": ([], "chalakudy_flood.py CELL, MARGIN"),
    "speckle_window": ([], "chalakudy_flood.py SPECKLE_WINDOW"),
    "geoid_offset_m": (["sentinel1", "copernicus_dem", "overture_water"], "chalakudy_flood.py main"),
    "water_threshold_db": (["sentinel1", "overture_water"], "chalakudy_flood.py main, otsu"),
    "reference_water": (["overture_water"], "chalakudy_flood.py water_reference_mask"),
    "permanent_water": (["sentinel1"], "chalakudy.py flood_masks"),
    "pre_event_scene": (["sentinel1"], "chalakudy.py flood_masks"),
    "flood_patch_min_cells": ([], "chalakudy.py flood_masks"),
    "warmup_s": ([], "chalakudy.py DAY0_S"),
    "protocols": (["ns3"], "sim/manet/manet.cc"),
    "wifi": (["ns3"], "sim/manet/manet.cc"),
    "payload_bytes": ([], "gen.py PAYLOAD_B"),
    "burst": (["kerala_exp"], "chalakudy.py BURST_PKTS, BURST_SPACING_S"),
    "deadline_s": ([], "chalakudy.py chalakudy_runs"),
    "seeds": ([], "run_experiment.py SEEDS"),
    "range_m": ([], "chalakudy.py chalakudy_runs; manet.cc --range"),
    "prop_formula": (["3gpp", "ns3"], "manet.cc --lossModel=logdistance"),
    "prop_condition": ([], "chalakudy.py PARAMS"),
    "frequency_mhz": (["ns3"], "chalakudy.py PARAMS"),
    "log_exponent": (["3gpp"], "manet.cc --logExponent"),
    "log_ref_loss_db": (["3gpp", "ns3"], "manet.cc --logRefLoss"),
    "effective_range_m": (["ns3"], "chalakudy.py PARAMS; range_m of chalakudy_prop runs"),
}

# derived data files: (path pattern, command that makes them)
DERIVED = [
    ("chalakudy_town_boundary.geojson", "python3 experiments/chalakudy_fetch.py boundary"),
    ("sentinel1_scenes.csv", "python3 experiments/chalakudy_fetch.py s1-scan START END (run for Jul-Sep and "
                             "Jan-May 2018; the scans merge into one file)"),
    ("flood/dem_copernicus_on_grid.tif", "python3 experiments/chalakudy_flood.py"),
    ("flood/reference_water_cells.tif", "python3 experiments/chalakudy_flood.py"),
    ("flood/geoid_offset_scan.csv", "python3 experiments/chalakudy_flood.py"),
    ("flood/scenes_processed.csv", "python3 experiments/chalakudy_flood.py"),
    ("flood/water_*.tif", "python3 experiments/chalakudy_flood.py"),
    ("buildings.csv", "python3 experiments/chalakudy.py prepare"),
    ("study_area.json", "python3 experiments/chalakudy.py prepare"),
    ("network_structure.csv", "python3 experiments/chalakudy.py network"),
    ("data_summary.json", "python3 experiments/chalakudy.py summary"),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def fmt_value(v):
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) < 1e4 else f"{v:.0f}"
    return str(v)


def main():
    missing = set(C.PARAMS) ^ set(USES)
    assert not missing, f"PARAMS and USES differ: {missing}"

    derived = []
    for pattern, cmd in DERIVED:
        for path in sorted(glob.glob(os.path.join(DATA, pattern))):
            derived.append(dict(file=os.path.relpath(path, C.REPO), bytes=os.path.getsize(path),
                                sha256=sha256(path), made_by=cmd))
    with open(os.path.join(DATA, "derived_files.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(derived[0]))
        w.writeheader()
        w.writerows(derived)

    kinds = {"measured": "MEASURED", "derived": "DERIVED", "assumed": "ASSUMED"}
    lines = [
        "# Chalakudy experiment: where every number comes from",
        "",
        "Generated by `python3 experiments/chalakudy_provenance.py` from `PARAMS` in `experiments/chalakudy.py`; "
        "edit those, not this file.",
        "",
        "Kinds: **MEASURED** = taken from a cited source (for a literature model, the source is cited but nothing "
        "was measured in Chalakudy); **DERIVED** = computed from measured data by a script in `experiments/`; "
        "**ASSUMED** = a choice, with the reasoning given, swept where it could change the result.",
        "",
        "## What is real data and what is not",
        "",
        "- **Real (measured):** the town boundary; the position and footprint of every building (Overture: "
        "Google Open Buildings, dated 2023-05-01 in Overture, and OpenStreetMap); ground height (Copernicus DEM, a surface model); rivers "
        "and ponds (OpenStreetMap); open water on 24 Sentinel-1 radar images from January to September 2018; "
        "the event dates (heavy rain 15-17 Aug, dam releases 14-18 Aug, Chalakudy flooding on 15 or 17 Aug, "
        "last Thrissur substation back on 27 Aug).",
        "- **Derived from it:** the study square; each building's ground estimate; flood-water maps and each "
        "building's distance to radar-visible flood water; the order in which devices fail (lowest ground first; "
        "in the study square no building is near radar-visible flood water, so ground height alone sets the "
        "order); network structure.",
        "- **Assumed (no data):** how many devices take part and which buildings have them; how many buildings "
        "flood at the peak (swept 10-50%); the rise of the water between onset and 18 Aug; that flooded devices "
        "do not return; when the power was cut (pending KSEB); battery size and charge (placeholders); the "
        "radio's energy use (ns-3 defaults, not a 2018 phone); message traffic; the 150 m radio range (with a "
        "cited path-loss model as sensitivity); time compression of 1 day = 30 s.",
        "",
        "## Data sources",
        "",
        "Checksums (SHA-256) of every downloaded file are in `downloads.csv`; raw files are kept out of git "
        "(`data/chalakudy/raw/`, about 170 MB) and are re-fetched by `experiments/chalakudy_fetch.py`. Derived "
        "files and their checksums are in `derived_files.csv`.",
        "",
        "| Key | Title | URL | Page / section | Accessed | Licence |",
        "|---|---|---|---|---|---|",
    ]
    for k, (title, url, page, when, lic) in SOURCES.items():
        lines.append(f"| `{k}` | {cell(title)} | {cell(url)} | {cell(page)} | {cell(when)} | {cell(lic)} |")
    lines += [
        "",
        "## Parameters",
        "",
        "| Parameter | Value | Kind | Source | Script | Reasoning | Range swept |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, p in C.PARAMS.items():
        src, script = USES[name]
        sweep = p["sweep"] if p["sweep"] is not None else "-"
        if isinstance(sweep, list):
            sweep = ", ".join(fmt_value(v) for v in sweep)
        lines.append(f"| `{name}` | {cell(fmt_value(p['value']))} | {kinds[p['kind']]} | "
                     f"{', '.join(f'`{s}`' for s in src) or '-'} | {cell(script)} | {cell(p['why'])} | "
                     f"{cell(sweep)} |")
    lines += [
        "",
        "## Derived data files",
        "",
        "| File | Made by |",
        "|---|---|",
    ]
    seen = set()
    for d in derived:
        key = (os.path.dirname(d["file"]), d["made_by"]) if "water_" in d["file"] else d["file"]
        if key in seen:
            continue
        seen.add(key)
        name = d["file"] if "water_" not in d["file"] else "data/chalakudy/flood/water_*.tif (24 files)"
        lines.append(f"| `{name}` | `{d['made_by']}` |")
    lines += [
        "",
        "`chalakudy_fetch.py boundary` and `chalakudy.py prepare` were rerun on 29 Oct 2026 and reproduced "
        "`chalakudy_town_boundary.geojson`, `buildings.csv` and `study_area.json` byte for byte.",
        "",
        "## Not obtained",
        "",
        "Census population and households, device ownership, the CWC water-level record, the KSEB power-cut "
        "date, a cited 2018 phone battery capacity, a bare-earth DEM and the Dartmouth flood map could not be "
        "fetched from this session (network policy). `MANUAL_DOWNLOADS.md` lists the exact files. Until they "
        "arrive the values they would set are ASSUMED above and nothing is substituted with a guess.",
        "",
    ]
    with open(os.path.join(DATA, "PROVENANCE.md"), "w") as fh:
        fh.write("\n".join(lines))
    print(f"wrote PROVENANCE.md ({len(C.PARAMS)} parameters, {len(SOURCES)} sources) and derived_files.csv "
          f"({len(derived)} files)")


if __name__ == "__main__":
    main()
