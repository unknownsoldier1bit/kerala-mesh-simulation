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
                         why="NS-3 can run about 50-150 nodes here; a 1 km square at 50-150 participating "
                             "devices gives mean degrees similar to the main grid. The whole 24.8 km2 town "
                             "would need ~2,800 nodes to be connected at 150 m range."),
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
                      sweep="area-weighted sampling compared on network structure only",
                      why="No data on which households would run the app."),
    "ground_estimate": dict(value="5th percentile of Copernicus DSM within 50 m of the building centroid",
                            kind="derived", sweep=None,
                            why="The DSM includes roofs and trees; the lowest nearby cell is the best "
                                "ground proxy available. Used only to rank buildings."),
    "observed_flood_buffer_m": dict(value=20.0, kind="assumed", sweep=[10.0, 20.0],
                                    why="A building counts as observed-flooded if Sentinel-1 flood water "
                                        "(21 Aug, patches >= 10 cells) lies within this distance."),
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
    "radio_power_model": dict(value="NS-3 WifiRadioEnergyModel defaults (idle 0.273 A at 3 V)",
                              kind="measured", sweep=None,
                              why="Checked in the ns-3.47 source (docs/ns3-defaults.md). These currents are not "
                                  "from a 2018 phone; only the Wi-Fi radio is modelled."),
    "day_s": dict(value=30.0, kind="assumed", sweep=None,
                  why="Time compression as in the kerala experiment (1 day = 30 simulated s), for "
                      "comparability; protocol timers are not compressed."),
    "flows": dict(value=20, kind="assumed", sweep=None, why="As in the kerala experiment."),
    "burst_mean_gap_s": dict(value=15.0, kind="assumed", sweep=[7.5, 15.0, 30.0],
                             why="Disaster message traffic is not documented (data/sources.md: missing)."),
    "range_m": dict(value=150.0, kind="assumed", sweep="log-distance propagation as sensitivity",
                    why="Same unit-disk radio as every other experiment, for comparability."),
}


def P(name):
    return PARAMS[name]["value"]


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
                   loss_model="range"):
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
                                            energy_j=0, energy_model="states",
                                            fail_time_s=meta["failure_start_s"], restore_time_s=None,
                                            traffic_start_s=DAY0_S, traffic_stop_s=SIM_END_S - 2,
                                            sim_time_s=SIM_END_S, payload_bytes=gen.PAYLOAD_B,
                                            range_m=P("range_m"), deadline_s=1.0,
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
    # feasibility pilot (run time, routing start-up): no flooding, seed 1 only; not part of the results
    "chalakudy_pilot": dict(onsets=(15,), batteries=("limited", "unlimited"), models=("control",), nodes=(100, 150)),
}


def runs_for(exp, protocols, seeds):
    return chalakudy_runs(exp, protocols, seeds, **VARIANTS[exp])


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
