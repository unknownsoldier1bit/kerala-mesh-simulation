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


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
