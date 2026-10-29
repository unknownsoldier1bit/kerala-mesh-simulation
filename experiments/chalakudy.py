"""Chalakudy experiment: mesh nodes at real building locations, flood failures from real 2018 data.

Every number used here is one of three kinds, and PARAMS below says which:
  MEASURED  taken from a source (cited in data/chalakudy/PROVENANCE.md)
  DERIVED   computed from cited data by a script in this repo
  ASSUMED   no data exists; the reason and the range swept are recorded

What comes from data:
  - the study area: a 1 km x 1 km square inside the Chalakudy municipality boundary
    (DataMeet / Kerala LSG delimitation map), chosen by a stated rule on the elevation data;
  - node positions: centroids of real building footprints (Overture Maps: OpenStreetMap and
    Google Open Buildings);
  - which nodes flood first: lowest ground first, from the Copernicus GLO-30 elevation model;
  - nodes whose building had Sentinel-1-visible flood water within 20 m on 21 Aug 2018 are
    always among the flooded (measured lower bound);
  - the timeline anchors in data/sources.md (dam releases 14-18 Aug, red rain 15-17 Aug,
    Chalakudy onset 15 or 17 Aug, last Thrissur substation back 27 Aug).

What is assumed (and swept): the share of buildings flooded at the peak, the number of
devices taking part in the mesh, battery charge and the share available to the radio,
radio power, message traffic and the time compression. See PARAMS.

Usage, from the repo root:
    python3 experiments/chalakudy.py prepare     # building table, study area, network stats
"""

import csv
import glob
import json
import os
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data", "chalakudy")
FLOOD = os.path.join(DATA, "flood")
UTM = "EPSG:32643"

# ---------------------------------------------------------------------------
# Parameters. kind: measured / derived / assumed. Values used by the code come from here.
# ---------------------------------------------------------------------------

PARAMS = {
    "study_side_m": dict(value=1000.0, kind="assumed", sweep=None,
                         why="ns-3 runs take minutes at 50-150 devices (pilot). In a 1 km square, 50, 100 and "
                             "150 devices at 150 m have mean degree 3.75, 7.2 and 10.8 "
                             "(data/chalakudy/network_structure.csv), within the range of the main grid's 25-50 "
                             "nodes (5.2-10.5). A larger area would need more devices than ns-3 can run here."),
    "study_area_rule": dict(value="1 km square, >= 99% inside the municipality, holding the most buildings "
                                  "among the municipality's lowest 25% by ground estimate", kind="assumed",
                            sweep="alternative rule reported (most buildings within 300 m of 21-Aug flood water)",
                            why="Ward boundaries are not available; the lowest-lying built-up square is the "
                                "best data-based stand-in for 'worst-flooded wards'."),
    "nodes": dict(value=100, kind="assumed", sweep=[50, 100, 150],
                  why="Number of devices in the square that run the mesh app. Census and phone-ownership "
                      "figures (pending, see MANUAL_DOWNLOADS.md) only change the implied participation "
                      "rate, not the simulation inputs."),
    "placement": dict(value="uniform over building footprints in the square (one device per sampled "
                            "building, at its centroid)", kind="assumed",
                      sweep="area-weighted sampling, compared on network structure only "
                            "(network_structure.csv)",
                      why="No data on which households would run the app. Drawing buildings in proportion to "
                          "footprint area instead changes the network little: mean degree 3.5/7.0/10.7 vs "
                          "3.75/7.2/10.8 and largest connected part 62/94/99% vs 61/97/99% at 50/100/150 devices "
                          "(150 m, seeds 1-10)."),
    "ground_estimate": dict(value="5th percentile of Copernicus DSM within 50 m of the building centroid",
                            kind="derived", sweep=None,
                            why="The DSM includes roofs and trees; the lowest nearby cell is the best "
                                "ground proxy available. Used only to rank buildings."),
    "observed_flood_buffer_m": dict(value=20.0, kind="assumed", sweep=None,
                                    why="A building counts as observed-flooded if Sentinel-1 flood water "
                                        "(21 Aug, patches >= 10 cells) lies within this distance. In the study "
                                        "square no building does (nearest 132 m on the 21 Aug descending pass, "
                                        "58 m ascending), so 10 m and 20 m give identical inputs (checked for "
                                        "50/100/150 devices, seeds 1-10) and no sweep is run. The failure order "
                                        "in the square therefore comes from ground height alone."),
    "peak_flooded_share": dict(value=0.25, kind="assumed", sweep=[0.10, 0.25, 0.50],
                               why="No building-level record of the peak. Sentinel-1 missed the peak "
                                   "(no image 10-20 Aug); the DEM is too canopy-biased for absolute levels."),
    "onset_day": dict(value=15, kind="measured", sweep=[15, 17],
                      why="Sources disagree (Deccan Herald: early 15 Aug; Scroll quoting an MP: 17 Aug); "
                          "both are run (data/sources.md)."),
    "peak_day": dict(value=18.0, kind="assumed", sweep=None,
                     why="Water rises from onset until 18 Aug 00:00: heavy rain 15-17 Aug and dam releases "
                         "until 18 Aug (data/sources.md)."),
    "flooded_nodes_return": dict(value=False, kind="assumed", sweep=None,
                                 why="Flooded households evacuate or lose their device; Sentinel-1 shows the "
                                     "water receding by 21-27 Aug, but there is no data on returns."),
    "power_cut_day": dict(value="onset day 00:00", kind="assumed", sweep=None,
                          why="KSEB cut-off date for Chalakudy not available (MANUAL_DOWNLOADS.md item 4)."),
    "power_back_day": dict(value=27, kind="measured", sweep=None,
                           why="Last Thrissur substation back 27 Aug (KSEB, data/sources.md); the run ends then."),
    "battery_capacity_mah": dict(value=3000.0, kind="assumed", sweep=None,
                                 why="Placeholder until a cited typical 2018 capacity is supplied "
                                     "(MANUAL_DOWNLOADS.md item 7). Scales with the swept share below."),
    "battery_voltage_v": dict(value=3.85, kind="assumed", sweep=None,
                              why="Typical Li-ion phone cell nominal voltage; placeholder like the capacity."),
    "radio_share_of_battery": dict(value=0.5, kind="assumed", sweep=[0.25, 0.5, 1.0],
                                   why="Share of the battery left for the mesh radio after the phone's other "
                                       "uses (screen, calls). No data."),
    "charge_at_power_cut": dict(value="uniform 20-100%", kind="assumed", sweep=None,
                                why="No data on charge levels when the power went."),
    "radio_power_model": dict(value="ns-3 WifiRadioEnergyModel default currents (idle 0.273 A at 3 V = 0.82 W)",
                              kind="assumed", sweep=None,
                              why="The brief asks for ns-3 defaults; the values were checked in the ns-3.47 source "
                                  "(docs/ns3-defaults.md). They are not measurements of a 2018 phone, and only the "
                                  "Wi-Fi radio is modelled (no screen, processor or cellular radio). With them, "
                                  "every device runs flat within 1-9 simulated s (1-7.5 real hours) of the power cut "
                                  "(pilot), whatever the protocol."),
    "day_s": dict(value=30.0, kind="assumed", sweep=None,
                  why="Time compression as in the kerala experiment (1 day = 30 simulated s), for "
                      "comparability; protocol timers are not compressed."),
    "flows": dict(value=20, kind="assumed", sweep=None, why="As in the kerala experiment."),
    "burst_mean_gap_s": dict(value=15.0, kind="assumed", sweep=[7.5, 15.0, 30.0],
                             why="Disaster message traffic is not documented (data/sources.md: missing)."),
    # Sentinel-1 flood mapping (experiments/chalakudy_flood.py)
    "s1_scenes": dict(value="24 Sentinel-1 IW GRDH scenes, VV, 5 Jan - 26 Sep 2018: 22 descending (relative "
                            "orbit 165; 21 from Sentinel-1A, 27 Aug from 1B) and 2 ascending (orbit 173; 21 Aug "
                            "1A, 27 Aug 1B)", kind="measured", sweep=None,
                      why="Every scene in the AWS archive covering the town in Jan-May and Jul-Sep 2018 "
                          "(data/chalakudy/sentinel1_scenes.csv). No image exists between 10 and 20 Aug, so the "
                          "flood peak was not observed."),
    "grid_cell_m": dict(value=10.0, kind="assumed", sweep=None,
                        why="The GRDH pixel spacing; grid = municipality plus 1 km margin, UTM 43N."),
    "speckle_window": dict(value="5 x 5 boxcar", kind="assumed", sweep=None,
                           why="A common, simple speckle filter; keeps 50 m-scale detail."),
    "geoid_offset_m": dict(value=-96.0, kind="derived", sweep=None,
                           why="Needed to place the radar image on the DEM (the geoid grid could not be "
                               "downloaded). Chosen as the offset, from -160 to -20 m in 4 m steps, that makes "
                               "mapped rivers and ponds darkest against their surroundings, averaged over 6 "
                               "descending scenes (flood/geoid_offset_scan.csv)."),
    "water_threshold_db": dict(value="Otsu threshold per scene: -10.6 to -12.9 dB (flood/scenes_processed.csv)",
                               kind="derived", sweep=None,
                               why="Computed on a balanced sample: reference water cells plus an equal number "
                                   "of land cells >= 150 m from mapped water (random seed 2018)."),
    "reference_water": dict(value="OSM water polygons >= 2,000 m2, shrunk by 15 m; comparison ring 60 m wide",
                            kind="assumed", sweep=None,
                            why="Large, permanent water bodies whose interior is surely water at 10 m cells."),
    "permanent_water": dict(value="water in >= 50% of the Jan-May 2018 descending scenes", kind="assumed",
                            sweep=None, why="Dry-season water is not flood water."),
    "pre_event_scene": dict(value="28 Jul 2018 (descending)", kind="assumed", sweep=None,
                            why="Last image before the August event; water already present then is not "
                                "counted as flood water."),
    "flood_patch_min_cells": dict(value=10, kind="assumed", sweep=None,
                                  why="Smallest flood patch kept: 10 cells (0.1 ha), to drop isolated dark "
                                      "pixels. An exploratory check of 1-25 cells (WORKLOG 07:12, not a "
                                      "committed script) found 8-31 of the town's 21,355 buildings within "
                                      "10-20 m of 21 Aug flood water, depending on this value."),
    # Simulation settings shared with the earlier experiments
    "warmup_s": dict(value=60.0, kind="assumed", sweep=None,
                     why="As in every experiment. Pilot check (rule 7): OLSR tables complete from 20 s; DSDV "
                         "reaches its steady level (96-99.7% of connected pairs routable) by 40-60 s and stays "
                         "there, so a longer warm-up would not change it."),
    "protocols": dict(value="AODV, OLSR, DSDV with ns-3.47 defaults", kind="assumed", sweep=None,
                      why="As in every experiment (docs/ns3-defaults.md)."),
    "wifi": dict(value="802.11b ad hoc, 11 Mbps data, 1 Mbps control, 16.0206 dBm, no RTS/CTS", kind="assumed",
                 sweep=None, why="As in every experiment; transmit power is the ns-3 default."),
    "payload_bytes": dict(value=512, kind="assumed", sweep=None, why="As in every experiment."),
    "burst": dict(value="5 packets, 0.2 s apart", kind="assumed", sweep=None, why="As in the kerala experiment."),
    "deadline_s": dict(value=1.0, kind="assumed", sweep=None,
                       why="The deadline T is still a placeholder in the project (CLAUDE.md); same as the "
                           "other experiments."),
    "seeds": dict(value="1-10, paired", kind="assumed", sweep=None,
                  why="Same seed = same devices, flows, failure times and batteries across protocols and "
                      "scenarios."),
    "range_m": dict(value=150.0, kind="assumed", sweep="log-distance propagation as sensitivity",
                    why="Same unit-disk radio as every other experiment, for comparability."),
    # Propagation sensitivity: a published path-loss formula instead of the unit disk, nothing tuned.
    "prop_formula": dict(value="PL = 36.85 + 30 log10(d) + 18.9 log10(f_GHz) dB", kind="measured",
                         sweep=None,
                         why="Cited empirical model, not a Chalakudy measurement: 3GPP TR 37.885 Table 6.2.1-1, "
                             "V2V Urban, NLOS (link blocked by buildings), as implemented in ns-3.47 "
                             "ThreeGppV2vUrbanPropagationLossModel::GetLossNlos. It is the 3GPP model for radios "
                             "near street level at both ends; it was made for vehicles, not houses."),
    "prop_condition": dict(value="NLOS for every link", kind="assumed", sweep=None,
                           why="Devices are at building positions in a town under dense tree cover, so most "
                               "links between them are blocked. The LOS formula of the same table would give "
                               "about 1.35 km and the walls of the houses (not modelled) would cut it further; "
                               "per-link line of sight would need tree and wall data that are not available."),
    "frequency_mhz": dict(value=2412.0, kind="derived", sweep=None,
                          why="ns-3 default operating channel for 802.11b: channel 1, 2412 MHz "
                              "(wifi-phy-operating-channel.cc)."),
    "log_exponent": dict(value=3.0, kind="derived", sweep=None, why="30 log10(d) in prop_formula."),
    "log_ref_loss_db": dict(value=36.85 + 18.9 * np.log10(2.412), kind="derived", sweep=None,
                            why="prop_formula at d = 1 m and 2412 MHz."),
    "effective_range_m": dict(value=round(10 ** ((16.0206 - (36.85 + 18.9 * np.log10(2.412)) + 82.0) / 30.0), 1),
                              kind="derived", sweep=None,
                              why="Distance at which received power falls to -82 dBm, the minimum RSSI of ns-3's "
                                  "default ThresholdPreambleDetectionModel, with the default 16.0206 dBm transmit "
                                  "power. A two-node sweep in sim/manet confirmed it: 100/100 packets at 62.5 m, "
                                  "0/100 at 63 m. Used as the link distance for the connectivity metrics."),
}


def P(name):
    return PARAMS[name]["value"]


SEEDS = range(1, 11)  # as in run_experiment.py


# ---------------------------------------------------------------------------
# Building table
# ---------------------------------------------------------------------------


def to_utm_fn():
    from pyproj import Transformer

    t = Transformer.from_crs(4326, UTM, always_xy=True)
    return lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1]))


def town_polygon_utm():
    import shapely
    from shapely.geometry import shape

    g = json.load(open(os.path.join(DATA, "chalakudy_town_boundary.geojson")))["features"][0]["geometry"]
    return shapely.transform(shape(g), to_utm_fn())


def flood_masks():
    """Permanent water, pre-event water (28 Jul) and observed flood water (21 Aug, both passes)."""
    import rasterio
    from scipy import ndimage

    def rd(name):
        return rasterio.open(os.path.join(FLOOD, name)).read(1)

    src = rasterio.open(os.path.join(FLOOD, "reference_water_cells.tif"))
    dry = [rasterio.open(p).read(1) for p in sorted(glob.glob(os.path.join(FLOOD, "water_2018-0[1-5]-*_des.tif")))]
    perm = np.mean(dry, axis=0) >= 0.5
    pre = rd("water_2018-07-28T0040_des.tif").astype(bool)
    out = {}
    for tag in ("2018-08-09T0040_des", "2018-08-21T0040_des", "2018-08-21T1306_asc", "2018-08-27T0040_des"):
        fl = rd(f"water_{tag}.tif").astype(bool) & ~pre & ~perm
        lab, n = ndimage.label(fl, structure=np.ones((3, 3)))
        sizes = ndimage.sum(fl, lab, index=np.arange(1, n + 1))
        out[tag] = np.isin(lab, np.flatnonzero(sizes >= 10) + 1)  # minimum patch: 10 cells (0.1 ha)
    return src.transform, perm, out


def building_table():
    """One row per building in the municipality: position, footprint, ground estimate, flood flags."""
    import pyarrow.parquet as pq
    import rasterio
    import shapely
    from scipy import ndimage

    town = town_polygon_utm()
    rows = pq.read_table(os.path.join(DATA, "raw", "overture", "building.parquet")).to_pylist()
    geoms = shapely.from_wkb([r["geometry"] for r in rows])
    f = to_utm_fn()
    geoms = np.array([shapely.transform(g, f) for g in geoms])
    cent = shapely.centroid(geoms)
    keep = shapely.contains(town, cent)
    rows = [r for r, k in zip(rows, keep) if k]
    geoms, cent = geoms[keep], cent[keep]
    xy = shapely.get_coordinates(cent)

    dem_src = rasterio.open(os.path.join(FLOOD, "dem_copernicus_on_grid.tif"))
    dem = dem_src.read(1)
    tr = dem_src.transform
    r = 5  # 50 m radius at 10 m cells
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    ground = ndimage.percentile_filter(dem, 5, footprint=(xx ** 2 + yy ** 2) <= r * r)
    col, row = (~tr) * (xy[:, 0], xy[:, 1])
    row, col = np.floor(row).astype(int), np.floor(col).astype(int)

    ftr, perm, floods = flood_masks()
    assert ftr == tr
    dist = {tag: ndimage.distance_transform_edt(~m) * 10.0 for tag, m in floods.items()}
    inv = ~tr

    def footprint_distance(d):
        out = np.empty(len(geoms))
        for i, g in enumerate(geoms):
            pts = np.vstack([shapely.get_coordinates(g), xy[i:i + 1]])
            c, rr = inv * (pts[:, 0], pts[:, 1])
            rr, c = np.floor(rr).astype(int), np.floor(c).astype(int)
            ok = (rr >= 0) & (rr < d.shape[0]) & (c >= 0) & (c < d.shape[1])
            out[i] = d[rr[ok], c[ok]].min() if ok.any() else np.inf
        return out

    table = []
    fd = {tag: footprint_distance(d) for tag, d in dist.items()}
    for i, rr in enumerate(rows):
        srcs = sorted({s.get("dataset") for s in (rr.get("sources") or [])})
        table.append(dict(
            building=i, overture_id=rr["id"], source=";".join(srcs), x=round(float(xy[i, 0]), 2),
            y=round(float(xy[i, 1]), 2), footprint_m2=round(float(shapely.area(geoms[i])), 1),
            surface_m=round(float(dem[row[i], col[i]]), 2), ground_est_m=round(float(ground[row[i], col[i]]), 2),
            **{f"flood_dist_m_{tag[:10]}_{tag[-3:]}": round(float(fd[tag][i]), 1) for tag in fd},
        ))
    return table


def write_csv(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def read_buildings():
    with open(os.path.join(DATA, "buildings.csv")) as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, v in r.items():
            if k not in ("overture_id", "source"):
                r[k] = float(v)
    return rows


# ---------------------------------------------------------------------------
# Study area
# ---------------------------------------------------------------------------


def choose_square(rows, score, side=None, step=50.0, min_inside=0.99):
    """The side x side square (axis-aligned in UTM) inside the town with the highest summed score."""
    import shapely
    from shapely.geometry import box

    side = side or P("study_side_m")
    town = town_polygon_utm()
    x = np.array([r["x"] for r in rows])
    y = np.array([r["y"] for r in rows])
    x0, y0, x1, y1 = town.bounds
    best = None
    for sx in np.arange(x0, x1 - side + 1e-9, step):
        for sy in np.arange(y0, y1 - side + 1e-9, step):
            sq = box(sx, sy, sx + side, sy + side)
            if shapely.area(shapely.intersection(sq, town)) < min_inside * side * side:
                continue
            inside = (x >= sx) & (x < sx + side) & (y >= sy) & (y < sy + side)
            sc = float(score[inside].sum())
            if best is None or sc > best[0]:
                best = (sc, sx, sy, int(inside.sum()))
    return best


def network_stats(xy, rng_m=None):
    rng_m = rng_m or P("range_m")
    g = gen.unit_disk_graph(xy, rng_m)
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    big = g.subgraph(comps[0])
    return dict(nodes=len(xy), links=g.number_of_edges(), mean_degree=round(2 * g.number_of_edges() / len(xy), 2),
                components=len(comps), largest_component_share=round(len(comps[0]) / len(xy), 3),
                isolated_nodes=sum(1 for c in comps if len(c) == 1),
                diameter_largest_component=nx.diameter(big) if len(big) > 1 else 0)


def prepare():
    os.makedirs(DATA, exist_ok=True)
    rows = building_table()
    write_csv(os.path.join(DATA, "buildings.csv"), rows)
    print(f"{len(rows)} buildings written to data/chalakudy/buildings.csv")

    ground = np.array([r["ground_est_m"] for r in rows])
    low = (ground <= np.percentile(ground, 25)).astype(float)
    sc_low = choose_square(rows, low)
    near21 = (np.array([r["flood_dist_m_2018-08-21_des"] for r in rows]) <= 300.0).astype(float)
    sc_flood = choose_square(rows, near21)
    area = dict(rule=P("study_area_rule"), side_m=P("study_side_m"), x0=sc_low[1], y0=sc_low[2],
                buildings=sc_low[3], score_lowest25pct_buildings=sc_low[0],
                alternative_rule="most buildings within 300 m of 21-Aug Sentinel-1 flood water",
                alternative_x0=sc_flood[1], alternative_y0=sc_flood[2], alternative_buildings=sc_flood[3],
                alternative_score=sc_flood[0], crs=UTM)
    gen.write_json(os.path.join(DATA, "study_area.json"), area)
    print(json.dumps(area, indent=1))


# ---------------------------------------------------------------------------
# Simulator inputs
# ---------------------------------------------------------------------------

DAY0_S = 60.0  # simulated time of 14 Aug 2018 00:00; 0-60 s is network warm-up
SIM_END_S = DAY0_S + 13 * 30.0  # 27 Aug 00:00 at 30 s per day
IDLE_W = 0.273 * 3.0  # ns-3 WifiRadioEnergyModel idle current x 3 V (docs/ns3-defaults.md)
LOW_BATTERY = 0.10  # the radio switches off at 10% of the initial energy (BasicEnergySource default)
BURST_PKTS, BURST_SPACING_S = 5, 0.2  # as in the kerala experiment


def day(d):
    """Simulated time of August day d (e.g. day(15) = 15 Aug 00:00)."""
    return DAY0_S + (d - 14) * P("day_s")


def square_buildings(rows):
    a = json.load(open(os.path.join(DATA, "study_area.json")))
    sel = [r for r in rows if a["x0"] <= r["x"] < a["x0"] + a["side_m"] and a["y0"] <= r["y"] < a["y0"] + a["side_m"]]
    return sel, (a["x0"], a["y0"])


def sample_nodes(sq, n, seed):
    rng = np.random.default_rng(700_000 + 1000 * n + seed)
    idx = np.sort(rng.choice(len(sq), size=n, replace=False))
    return [sq[i] for i in idx]


def component_flows(g, n_flows, seed, gap_s, t_start, t_stop):
    """Random source-destination pairs in the same connected part, at least 2 hops apart, sending bursts."""
    rng = np.random.default_rng(710_000 + 1000 * len(g) + seed)
    pairs = []
    for comp in nx.connected_components(g):
        sub = g.subgraph(comp)
        hops = dict(nx.all_pairs_shortest_path_length(sub))
        pairs += [(a, b, hops[a][b]) for a in sub for b in sub if a < b and hops[a][b] >= 2]
    order = rng.permutation(len(pairs))
    flows = []
    for k in order[:n_flows]:
        a, b, h = pairs[k]
        if rng.random() < 0.5:
            a, b = b, a
        flows.append({"flow": len(flows), "src": int(a), "dst": int(b), "hops": int(h)})
    for f in flows:
        segs = []
        t = t_start + rng.exponential(gap_s)
        while t + BURST_PKTS * BURST_SPACING_S < t_stop:
            segs.append((t, t + BURST_PKTS * BURST_SPACING_S - 1e-6, BURST_SPACING_S))
            t += BURST_PKTS * BURST_SPACING_S + rng.exponential(gap_s)
        f["segments"] = segs
    return flows


def flood_order(nodes, buffer_m):
    """Indices of nodes, observed-flooded first (Sentinel-1, 21 Aug), then lowest ground first."""
    obs = [i for i, r in enumerate(nodes) if r["flood_dist_m_2018-08-21_des"] <= buffer_m]
    rest = sorted((i for i in range(len(nodes)) if i not in obs), key=lambda i: (nodes[i]["ground_est_m"], i))
    obs = sorted(obs, key=lambda i: (nodes[i]["ground_est_m"], i))
    return obs + rest, len(obs)


def flood_events(order, n_observed, n, share, onset):
    k = max(round(share * n), n_observed)
    t0, t1 = day(onset), day(P("peak_day"))
    return [(round(t0 + (r + 0.5) / k * (t1 - t0), 3), "fail", "node", int(v), -1, "flood")
            for r, v in enumerate(order[:k])]


def battery_energy(n, seed, onset, share_for_radio):
    """Initial energy (simulated J) so each battery empties after the power cut as a real phone would.

    After the cut the radio has soc x share x capacity x voltage (real J). Time compression turns
    that into simulated J (x day_s / 86400). Before the cut the battery is assumed full enough to
    cover idling until then, so idle energy until the cut is added, and the total is divided by 0.9
    because the radio switches off at 10% of the initial energy."""
    rng = np.random.default_rng(720_000 + 1000 * n + seed)
    soc = rng.uniform(0.2, 1.0, size=n)
    real_j = soc * share_for_radio * P("battery_capacity_mah") / 1000 * P("battery_voltage_v") * 3600
    sim_j = real_j * P("day_s") / 86400
    return (sim_j + IDLE_W * day(onset)) / (1 - LOW_BATTERY), soc


def chalakudy_runs(exp, protocols, seeds, onsets=(15,), batteries=("unlimited",), nodes=(100,),
                   shares=(0.25,), radio_shares=(0.5,), gaps=(15.0,), models=("flood", "uniform", "control"),
                   loss_model="range", flowmon=False, energy_model="states"):
    rows = read_buildings()
    sq, origin = square_buildings(rows)
    runs = []
    for n in nodes:
        for seed in seeds:
            picked = sample_nodes(sq, n, seed)
            xy = np.array([[r["x"] - origin[0], r["y"] - origin[1]] for r in picked])
            g = gen.unit_disk_graph(xy, P("range_m"))
            idir = os.path.join("results", exp, "inputs", f"n{n}_s{seed}")
            os.makedirs(os.path.join(REPO, idir), exist_ok=True)
            topo = os.path.join(idir, "topology.csv")
            gen.write_topology(os.path.join(REPO, topo), xy)
            write_csv(os.path.join(REPO, idir, "nodes.csv"),
                      [dict(node=i, building=int(r["building"]), overture_id=r["overture_id"], source=r["source"],
                            utm_x=r["x"], utm_y=r["y"], ground_est_m=r["ground_est_m"],
                            flood_dist_m_21aug=r["flood_dist_m_2018-08-21_des"]) for i, r in enumerate(picked)])
            gen.write_json(os.path.join(REPO, idir, "network.json"), dict(network_stats(xy), origin_utm=origin))
            order, n_obs = flood_order(picked, P("observed_flood_buffer_m"))
            for gap in gaps:
                fl = component_flows(g, P("flows"), seed, gap, DAY0_S, SIM_END_S - 2)
                ffile = os.path.join(idir, f"flows_gap{gap:g}.csv")
                gen.write_flows(os.path.join(REPO, ffile), fl)
                for onset in onsets:
                    for model in models:
                        for share in (shares if model != "control" else (None,)):
                            if model == "control":
                                events = []
                            else:
                                events = flood_events(order, n_obs, n, share, onset)
                                if model == "uniform":
                                    rng = np.random.default_rng(730_000 + 1000 * n + 10 * seed + onset
                                                                + int(100 * share))
                                    pick = rng.permutation(n)[:len(events)]
                                    events = sorted((t, a, k, int(v), b, "random")
                                                    for (t, a, k, _, b, _), v in zip(events, pick))
                            tag = model if model == "control" else f"{model}{int(round(100 * share))}"
                            efile = os.path.join(idir, f"events_{tag}_on{onset}.csv")
                            gen.write_events(os.path.join(REPO, efile), events)
                            failed = [e[3] for e in events]
                            h = g.copy()
                            h.remove_nodes_from(failed)
                            meta = dict(
                                scenario=tag, onset_day=onset, selection={"flood": "observed-flooded first, then "
                                "lowest ground first (Sentinel-1 + Copernicus DEM)", "uniform": "uniformly random "
                                "(seeded), same count and times", "control": "none"}[model],
                                failure_start_s=events[0][0] if events else None, failure_end_s=None,
                                n_failed_nodes=len(failed), pct_failed_nodes=round(100 * len(failed) / n, 2),
                                n_observed_flooded_in_sample=n_obs, n_failed_links=0, pct_failed_links=0.0,
                                components_at_peak=nx.number_connected_components(h) if len(h) else 0,
                                failed_nodes=[dict(node=int(e[3]), time_s=e[0],
                                                   building=int(picked[e[3]]["building"]),
                                                   x=round(float(xy[e[3]][0]), 1), y=round(float(xy[e[3]][1]), 1),
                                                   ground_est_m=picked[e[3]]["ground_est_m"]) for e in events])
                            gen.write_json(os.path.join(REPO, idir, f"scenario_{tag}_on{onset}.json"), meta)
                            for batt in batteries:
                                for rs in (radio_shares if batt == "limited" else (None,)):
                                    bfile = ""
                                    if batt == "limited":
                                        e0, soc = battery_energy(n, seed, onset, rs)
                                        bfile = os.path.join(idir, f"battery_on{onset}_r{int(round(100 * rs))}.csv")
                                        with open(os.path.join(REPO, bfile), "w") as fh:
                                            fh.write("node,initial_J\n")
                                            fh.writelines(f"{i},{v:.4f}\n" for i, v in enumerate(e0))
                                    btag = "nobatt" if batt == "unlimited" else f"batt{int(round(100 * rs))}"
                                    for proto in protocols:
                                        rid = f"{proto}_{tag}_on{onset}_{btag}_g{gap:g}_n{n}_s{seed}"
                                        runs.append(dict(
                                            experiment=exp, run_id=rid, protocol=proto, scenario=model,
                                            nodes=n, seed=seed, rng_run=seed, n_flows=len(fl), severity=share,
                                            severity_label=(f"{len(failed)} nodes flooded ({meta['pct_failed_nodes']}%)"
                                                            if failed else "no flooding"),
                                            onset_day=onset, battery=btag, burst_gap_s=gap, loss_model=loss_model,
                                            topo=topo, flows_file=ffile, events_file=efile, energy_file=bfile,
                                            energy_j=0, energy_model=energy_model, flowmon=flowmon,
                                            fail_time_s=meta["failure_start_s"], restore_time_s=None,
                                            traffic_start_s=DAY0_S, traffic_stop_s=SIM_END_S - 2,
                                            sim_time_s=SIM_END_S, payload_bytes=gen.PAYLOAD_B,
                                            range_m=(P("range_m") if loss_model == "range"
                                                     else P("effective_range_m")),
                                            log_exponent=P("log_exponent"), log_ref_loss_db=P("log_ref_loss_db"),
                                            deadline_s=1.0,
                                            windows={"before_onset": [day(14), day(onset)],
                                                     "acute": [day(onset), day(18)],
                                                     "sustained": [day(18), SIM_END_S - 2]},
                                            timeseries=True, connectivity=True, flows=fl))
    return runs


# Experiment variants: the main configuration and one-at-a-time sensitivity sweeps.
VARIANTS = {
    "chalakudy": dict(onsets=(15, 17), batteries=("limited", "unlimited")),
    "chalakudy_share": dict(onsets=(15,), shares=(0.10, 0.50), models=("flood", "uniform")),
    "chalakudy_nodes": dict(onsets=(15,), nodes=(50, 150)),
    "chalakudy_traffic": dict(onsets=(15,), gaps=(7.5, 30.0)),
    "chalakudy_battery": dict(onsets=(15,), batteries=("limited",), radio_shares=(0.25, 1.0)),
    # propagation sensitivity: same devices, flows and failures as the main runs, log-distance radio
    "chalakudy_prop": dict(onsets=(15,), loss_model="logdistance"),
    # cross-checks, 50 devices, seeds 1-2: ns-3 FlowMonitor vs this project's packet tracker, and the ns-3
    # energy framework vs the state-based energy count (allowed at <= 50 nodes; no radio is ever restored)
    "chalakudy_check": dict(onsets=(15,), batteries=("limited", "unlimited"), nodes=(50,), flowmon=True,
                            energy_model="ns3", seeds=(1, 2)),
    # feasibility pilot (run time, routing start-up): no flooding, seed 1 only; not part of the results
    "chalakudy_pilot": dict(onsets=(15,), batteries=("limited", "unlimited"), models=("control",), nodes=(100, 150)),
}


def runs_for(exp, protocols, seeds):
    v = dict(VARIANTS[exp])
    return chalakudy_runs(exp, protocols, v.pop("seeds", seeds), **v)


def network_table():
    """Network structure (unit-disk graph) of the sampled Chalakudy devices at the main range and at the
    log-distance effective range, for more device counts than can be simulated, plus the main grid's
    topologies for comparison. Writes data/chalakudy/network_structure.csv."""
    rows = read_buildings()
    sq, origin = square_buildings(rows)
    out = []
    for rng_m in (P("range_m"), P("effective_range_m")):
        for n in (50, 100, 150, 300, 500, 800, 1000, len(sq)):
            for seed in (SEEDS if n < len(sq) else (1,)):
                picked = sample_nodes(sq, n, seed) if n < len(sq) else sq
                xy = np.array([[r["x"] - origin[0], r["y"] - origin[1]] for r in picked])
                st = network_stats(xy, rng_m) if n <= 300 else dict(network_stats_fast(xy, rng_m))
                out.append(dict(source="chalakudy" if n < len(sq) else "chalakudy_all_buildings",
                                placement="uniform", range_m=rng_m, seed=seed, **st))
    # placement sensitivity: buildings drawn with probability proportional to footprint area
    area = np.array([r["footprint_m2"] for r in sq], dtype=float)
    for n in (50, 100, 150):
        for seed in SEEDS:
            rng = np.random.default_rng(740_000 + 1000 * n + seed)
            idx = np.sort(rng.choice(len(sq), size=n, replace=False, p=area / area.sum()))
            xy = np.array([[sq[i]["x"] - origin[0], sq[i]["y"] - origin[1]] for i in idx])
            out.append(dict(source="chalakudy", placement="area_weighted", range_m=P("range_m"), seed=seed,
                            **network_stats(xy)))
    for path in sorted(glob.glob(os.path.join(REPO, "results", "main", "inputs", "n*_s*", "topology.csv"))):
        with open(path) as fh:
            xy = np.array([[float(r["x"]), float(r["y"])] for r in csv.DictReader(fh)])
        seed = int(os.path.basename(os.path.dirname(path)).split("_s")[1])
        out.append(dict(source="main_grid", placement="uniform random in a 500 m square, redrawn until connected", range_m=P("range_m"), seed=seed,
                        **network_stats(xy)))
    write_csv(os.path.join(DATA, "network_structure.csv"), out)
    df = {}
    for r in out:
        df.setdefault((r["source"], r["placement"], r["range_m"], r["nodes"]), []).append(r)
    print("source, placement, range_m, nodes: mean degree, largest connected part (mean, min), components")
    for k, v in sorted(df.items()):
        print(k, round(np.mean([r["mean_degree"] for r in v]), 2),
              round(np.mean([r["largest_component_share"] for r in v]), 3),
              round(min(r["largest_component_share"] for r in v), 3),
              round(np.mean([r["components"] for r in v]), 1))


def network_stats_fast(xy, rng_m):
    """network_stats without the diameter, which is too slow to compute for large graphs."""
    g = gen.unit_disk_graph(xy, rng_m)
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    return dict(nodes=len(xy), links=g.number_of_edges(), mean_degree=round(2 * g.number_of_edges() / len(xy), 2),
                components=len(comps), largest_component_share=round(len(comps[0]) / len(xy), 3),
                isolated_nodes=sum(1 for c in comps if len(c) == 1), diameter_largest_component=None)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "network":
        network_table()
