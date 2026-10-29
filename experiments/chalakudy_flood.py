"""Maps open water around Chalakudy from Sentinel-1 radar images (2018).

Calm open water reflects radar away from the satellite, so it looks dark (low backscatter,
sigma0) in a radar image; land looks brighter. This script turns each Sentinel-1 GRD
image over Chalakudy into a water map on a 10 m grid:

1. Read only the part of the VV image that covers the study area (HTTP range reads).
2. Calibrate the digital numbers to sigma0 with the image's own calibration and thermal-noise
   tables (sigma0 = (DN^2 - noise) / A_sigma^2, as defined in the Sentinel-1 product format).
3. Reduce speckle with a 5 x 5 moving average (in linear units).
4. Put each pixel at its true position. GRD images are positioned on a reference surface
   whose height is given per image line in the annotation; a ground point lower than that
   surface appears shifted away from the satellite by (h_ref - h) / tan(incidence). h is the
   point's ellipsoidal height: Copernicus DEM height (relative to the EGM2008 geoid) plus the
   local geoid undulation N. N is not available offline here (the geoid grid server is
   blocked), so it is estimated from the data: the value that best lines up dark radar pixels
   with mapped water bodies (OSM river and large ponds, via Overture).
5. Classify water with Otsu's threshold (N. Otsu, "A threshold selection method from
   gray-level histograms", IEEE Trans. Systems, Man, and Cybernetics 9(1):62-66, 1979).
   Otsu needs a histogram with two comparable classes, but water covers only a few per
   cent of the area, so the threshold is computed per image on a balanced sample: every
   cell well inside a mapped river or large pond, plus the same number of cells drawn at
   random (fixed seed) from land at least 150 m from any mapped water.

Outputs go to data/chalakudy/flood/ (small GeoTIFFs and a CSV of thresholds).

Usage, from the repo root:
    python3 experiments/chalakudy_flood.py            # all scenes in sentinel1_scenes.csv
"""

import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chalakudy_fetch as fetch  # noqa: E402

REPO = fetch.REPO
DATA = fetch.DATA
OUT = os.path.join(DATA, "flood")
RAW_S1 = os.path.join(fetch.RAW, "s1")
DEM_FILE = os.path.join(fetch.RAW, "dem", "Copernicus_DSM_COG_10_N10_00_E076_00_DEM.tif")
BOUNDARY = os.path.join(DATA, "chalakudy_town_boundary.geojson")

UTM = "EPSG:32643"  # UTM zone 43N
CELL = 10.0  # grid cell size (m), the GRDH pixel spacing
MARGIN = 1000.0  # grid extends this far beyond the municipality (m)
SPECKLE_WINDOW = 5

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tiff,.tif")


# ---------------------------------------------------------------------------
# Study grid
# ---------------------------------------------------------------------------


def study_grid():
    """10 m UTM grid around the municipality: (transform, shape, x, y of cell centres)."""
    import shapely
    from shapely.geometry import shape

    g = json.load(open(BOUNDARY))["features"][0]["geometry"]
    to_utm = Transformer.from_crs(4326, UTM, always_xy=True)
    poly = shapely.transform(shape(g), lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1])))
    x0, y0, x1, y1 = poly.bounds
    x0, y0 = np.floor((x0 - MARGIN) / CELL) * CELL, np.floor((y0 - MARGIN) / CELL) * CELL
    x1, y1 = np.ceil((x1 + MARGIN) / CELL) * CELL, np.ceil((y1 + MARGIN) / CELL) * CELL
    w, h = int((x1 - x0) / CELL), int((y1 - y0) / CELL)
    transform = from_origin(x0, y1, CELL, CELL)
    xs = x0 + CELL * (np.arange(w) + 0.5)
    ys = y1 - CELL * (np.arange(h) + 0.5)
    return transform, (h, w), xs, ys


def dem_on_grid(transform, shape_):
    out = np.full(shape_, np.nan, dtype="float32")
    with rasterio.open(DEM_FILE) as src:
        reproject(rasterio.band(src, 1), out, dst_transform=transform, dst_crs=UTM, resampling=Resampling.bilinear)
    return out


def write_tif(path, arr, transform, nodata=None, dtype=None):
    arr = np.asarray(arr)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=dtype or arr.dtype, crs=UTM, transform=transform, nodata=nodata,
                       compress="deflate") as dst:
        dst.write(arr.astype(dtype or arr.dtype), 1)


# ---------------------------------------------------------------------------
# Sentinel-1 product metadata
# ---------------------------------------------------------------------------


def s1_file(scene_path, name):
    """Fetches a small product file once and keeps it under data/chalakudy/raw/s1/."""
    local = os.path.join(RAW_S1, os.path.basename(scene_path.rstrip("/")), name)
    if not os.path.exists(local):
        fetch.download(f"{fetch.S1_BUCKET}/{scene_path.rstrip('/')}/{name}", local)
    return local


def geolocation(ann):
    pts = ann.findall(".//geolocationGridPoint")
    g = {k: np.array([float(p.find(k).text) for p in pts]) for k in
         ("line", "pixel", "latitude", "longitude", "height", "incidenceAngle")}
    return g


def poly_terms(a, b, deg=3):
    return np.stack([a ** i * b ** j for i in range(deg + 1) for j in range(deg + 1 - i)], axis=-1)


class Geometry:
    """Polynomial maps between image (line, pixel) and map (UTM x, y) around the study area."""

    def __init__(self, g, center_xy, radius=40_000.0):
        to_utm = Transformer.from_crs(4326, UTM, always_xy=True)
        x, y = to_utm.transform(g["longitude"], g["latitude"])
        near = np.hypot(x - center_xy[0], y - center_xy[1]) < radius
        if near.sum() < 12:
            near = np.argsort(np.hypot(x - center_xy[0], y - center_xy[1]))[:20]
        self.x0, self.y0 = center_xy
        self.l0, self.p0 = g["line"][near].mean(), g["pixel"][near].mean()
        xs, ys = (x[near] - self.x0) / 1e4, (y[near] - self.y0) / 1e4
        ls, ps = (g["line"][near] - self.l0) / 1e4, (g["pixel"][near] - self.p0) / 1e4
        A = poly_terms(xs, ys)
        self.c_line = np.linalg.lstsq(A, ls, rcond=None)[0]
        self.c_pix = np.linalg.lstsq(A, ps, rcond=None)[0]
        B = poly_terms(ls, ps)
        self.c_x = np.linalg.lstsq(B, xs, rcond=None)[0]
        self.c_y = np.linalg.lstsq(B, ys, rcond=None)[0]
        self.c_inc = np.linalg.lstsq(B, g["incidenceAngle"][near], rcond=None)[0]
        self.c_href = np.linalg.lstsq(B, g["height"][near], rcond=None)[0]
        # fit quality at the grid points (pixels)
        self.residual_px = float(np.max(np.hypot((A @ self.c_line - ls) * 1e4, (A @ self.c_pix - ps) * 1e4)))

    def to_image(self, x, y):
        T = poly_terms((x - self.x0) / 1e4, (y - self.y0) / 1e4)
        return T @ self.c_line * 1e4 + self.l0, T @ self.c_pix * 1e4 + self.p0

    def at_image(self, line, pixel):
        T = poly_terms((line - self.l0) / 1e4, (pixel - self.p0) / 1e4)
        x = T @ self.c_x * 1e4 + self.x0
        y = T @ self.c_y * 1e4 + self.y0
        return x, y, T @ self.c_inc, T @ self.c_href


def lut(root, vec_tag, val_tag):
    """Bilinear look-up table over (line, pixel) from calibration or noise vectors.

    Vectors may list slightly different pixel positions; each is resampled onto the first
    vector's pixel positions before building the grid."""
    vecs = root.findall(f".//{vec_tag}")
    lines = np.array([int(v.find("line").text) for v in vecs])
    pix = np.array([int(p) for p in vecs[0].find("pixel").text.split()])
    rows = []
    for v in vecs:
        vp = np.array([int(p) for p in v.find("pixel").text.split()])
        vals = np.array([float(t) for t in v.find(val_tag).text.split()])
        rows.append(vals if np.array_equal(vp, pix) else np.interp(pix, vp, vals))
    return RegularGridInterpolator((lines, pix), np.array(rows), bounds_error=False, fill_value=None)


def noise_lut(noi):
    """Range noise LUT: 'noiseRangeVector' (processor IPF >= 2.9) or 'noiseVector' (older products)."""
    if noi.find(".//noiseRangeVector") is not None:
        return lut(noi, "noiseRangeVector", "noiseRangeLut")
    return lut(noi, "noiseVector", "noiseLut")


# ---------------------------------------------------------------------------
# One scene
# ---------------------------------------------------------------------------


N_RANGE = (-160.0, -20.0)  # geoid offsets considered (m); the window read covers all of them


class Scene:
    """One Sentinel-1 image, calibrated and despeckled once over a window covering the study grid."""

    def __init__(self, scene, grid, dem):
        self.scene = scene
        transform, self.shape, xs, ys = grid
        path = scene["path"] + "/"
        ann = ET.parse(s1_file(path, "annotation/iw-vv.xml")).getroot()
        cal = ET.parse(s1_file(path, "annotation/calibration/calibration-iw-vv.xml")).getroot()
        noi = ET.parse(s1_file(path, "annotation/calibration/noise-iw-vv.xml")).getroot()
        g = geolocation(ann)
        X, Y = np.meshgrid(xs, ys)
        self.X, self.Y = X.ravel(), Y.ravel()
        self.geo = Geometry(g, (X.mean(), Y.mean()))
        l_c, p_c = self.geo.to_image(self.X, self.Y)
        x_a, y_a, inc, href = self.geo.at_image(l_c, p_c)
        x_b, y_b, _, _ = self.geo.at_image(l_c, p_c + 100.0)
        norm = np.hypot(x_b - x_a, y_b - y_a)
        self.ux, self.uy = (x_b - x_a) / norm, (y_b - y_a) / norm  # towards far range
        self.tan_inc, self.href, self.inc = np.tan(np.radians(inc)), href, inc
        self.dem = dem.ravel().astype(float)

        corners = [self.image_coords(n) for n in N_RANGE]
        ls = np.concatenate([c[0] for c in corners])
        ps = np.concatenate([c[1] for c in corners])
        pad = 3 * SPECKLE_WINDOW + 5
        r0, r1 = int(np.floor(np.nanmin(ls))) - pad, int(np.ceil(np.nanmax(ls))) + pad
        c0, c1 = int(np.floor(np.nanmin(ps))) - pad, int(np.ceil(np.nanmax(ps))) + pad
        url = f"/vsicurl/{fetch.S1_BUCKET}/{path}measurement/iw-vv.tiff"
        with rasterio.open(url) as src:
            r0, c0 = max(r0, 0), max(c0, 0)
            r1, c1 = min(r1, src.height), min(c1, src.width)
            dn = src.read(1, window=((r0, r1), (c0, c1))).astype("float64")
        L, P = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing="ij")
        pts = np.stack([L.ravel(), P.ravel()], axis=-1)
        a_sigma = lut(cal, "calibrationVector", "sigmaNought")(pts).reshape(L.shape)
        noise = noise_lut(noi)(pts).reshape(L.shape)
        if noi.find(".//noiseAzimuthVector") is not None:
            noise = noise * azimuth_noise(noi, L, P)
        floor = 1e-6 * max(float(dn.max()) ** 2, 1.0)
        sigma0 = np.maximum(dn ** 2 - noise, floor) / a_sigma ** 2
        sigma0 = ndimage.uniform_filter(sigma0, SPECKLE_WINDOW, mode="nearest")
        self.interp = RegularGridInterpolator((np.arange(r0, r1), np.arange(c0, c1)), sigma0, bounds_error=False,
                                              fill_value=np.nan)
        self.window = (r0, r1, c0, c1)

    def image_coords(self, geoid_n):
        h = self.dem + geoid_n  # ellipsoidal height of the ground
        # a point lower than the reference surface appears further from the satellite
        shift = (self.href - h) / self.tan_inc
        return self.geo.to_image(self.X + shift * self.ux, self.Y + shift * self.uy)

    def sigma0_db(self, geoid_n):
        l_img, p_img = self.image_coords(geoid_n)
        s0 = self.interp(np.stack([l_img, p_img], axis=-1)).reshape(self.shape)
        with np.errstate(divide="ignore", invalid="ignore"):
            return (10 * np.log10(s0)).astype("float32")

    def meta(self):
        r0, r1, c0, c1 = self.window
        return dict(geometry_fit_residual_px=round(self.geo.residual_px, 3), window_rows=f"{r0}-{r1}",
                    window_cols=f"{c0}-{c1}", incidence_deg_mean=round(float(np.nanmean(self.inc)), 3),
                    reference_height_m_mean=round(float(np.nanmean(self.href)), 2))


def azimuth_noise(noi, L, P):
    """Azimuth noise LUT (IPF >= 2.9): piecewise blocks over line/pixel ranges, each with its own LUT."""
    out = np.ones(L.shape)
    for v in noi.findall(".//noiseAzimuthVector"):
        p0, p1 = int(v.find("firstRangeSample").text), int(v.find("lastRangeSample").text)
        lines = np.array([int(t) for t in v.find("line").text.split()])
        vals = np.array([float(t) for t in v.find("noiseAzimuthLut").text.split()])
        sel = (P >= p0) & (P <= p1)
        if sel.any():
            out[sel] = np.interp(L[sel], lines, vals)
    return out


# ---------------------------------------------------------------------------
# Water reference polygons (for estimating the geoid offset) and thresholds
# ---------------------------------------------------------------------------


def water_reference_mask(grid, min_area_m2=2000.0, inner_buffer=-15.0):
    """Cells well inside mapped rivers and large ponds (OSM via Overture), for alignment."""
    import pyarrow.parquet as pq
    import shapely
    from rasterio.features import rasterize

    transform, shape_, _, _ = grid
    t = pq.read_table(os.path.join(fetch.RAW, "overture", "water.parquet")).to_pylist()
    to_utm = Transformer.from_crs(4326, UTM, always_xy=True)
    polys = []
    for r in t:
        if r.get("subtype") not in ("river", "pond", "lake", "reservoir", "water"):
            continue
        g = shapely.from_wkb(r["geometry"])
        if g.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        g = shapely.transform(g, lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1])))
        if g.area < min_area_m2:
            continue
        g = g.buffer(inner_buffer)
        if not g.is_empty:
            polys.append(g)
    inside = rasterize([(p, 1) for p in polys], out_shape=shape_, transform=transform, fill=0, dtype="uint8")
    outer = rasterize([(p.buffer(-inner_buffer + 60.0), 1) for p in polys], out_shape=shape_, transform=transform,
                      fill=0, dtype="uint8")
    ring = (outer == 1) & (inside == 0)
    return inside.astype(bool), ring


def otsu(values, bins=256):
    v = values[np.isfinite(values)]
    hist, edges = np.histogram(v, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1)
    m1 = (np.sum(hist * centers) - np.cumsum(hist * centers)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(centers[np.argmax(between)])


def main():
    os.makedirs(OUT, exist_ok=True)
    grid = study_grid()
    transform, shape_, _, _ = grid
    dem = dem_on_grid(transform, shape_)
    write_tif(os.path.join(OUT, "dem_copernicus_on_grid.tif"), dem, transform, dtype="float32")
    inside, ring = water_reference_mask(grid)
    far_land = np.flatnonzero((ndimage.distance_transform_edt(~inside) >= 150.0 / CELL).ravel())
    land_sample = np.unravel_index(np.random.default_rng(2018).choice(far_land, size=int(inside.sum()),
                                                                      replace=False), inside.shape)
    write_tif(os.path.join(OUT, "reference_water_cells.tif"), inside.astype("uint8"), transform, dtype="uint8")
    scenes = list(csv.DictReader(open(os.path.join(DATA, "sentinel1_scenes.csv"))))
    only = sys.argv[1:]
    if only:
        scenes = [s for s in scenes if any(o in s["id"] for o in only)]

    # 1. Geoid offset: the N that makes mapped water darkest relative to its surroundings,
    #    averaged over several descending scenes from the dry season and the monsoon.
    calib_ids = [s for s in scenes if s["pass_direction"] == "descending"][:: max(1, len(scenes) // 6)][:6]
    candidates = np.arange(N_RANGE[0], N_RANGE[1] + 1e-9, 4.0)
    contrast = np.zeros((len(calib_ids), len(candidates)))
    for i, s in enumerate(calib_ids):
        sc = Scene(s, grid, dem)
        for j, n in enumerate(candidates):
            db = sc.sigma0_db(n)
            contrast[i, j] = np.nanmean(db[ring]) - np.nanmean(db[inside])
        print(f"geoid scan {s['start_utc'][:10]}: best N = {candidates[np.argmax(contrast[i])]:.0f} m", flush=True)
    mean_c = contrast.mean(axis=0)
    geoid_n = float(candidates[np.argmax(mean_c)])
    with open(os.path.join(OUT, "geoid_offset_scan.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["geoid_n_m"] + [s["start_utc"][:10] for s in calib_ids] + ["mean_contrast_db"])
        for j, n in enumerate(candidates):
            w.writerow([n] + [round(c, 4) for c in contrast[:, j]] + [round(mean_c[j], 4)])
    print(f"estimated geoid offset N = {geoid_n:.0f} m (contrast {mean_c.max():.2f} dB)", flush=True)

    # 2. Every scene on the grid, with its Otsu threshold
    rows = []
    for s in scenes:
        sc = Scene(s, grid, dem)
        db, meta = sc.sigma0_db(geoid_n), sc.meta()
        date = s["start_utc"][:16].replace(":", "")
        tag = f"{date}_{s['pass_direction'][:3]}"
        write_tif(os.path.join(OUT, f"sigma0_db_{tag}.tif"), db, transform, nodata=np.nan, dtype="float32")
        land = db[land_sample]
        t = otsu(np.concatenate([db[inside], db[land_sample]]))
        water = (db < t) & np.isfinite(db)
        write_tif(os.path.join(OUT, f"water_{tag}.tif"), water.astype("uint8"), transform, dtype="uint8")
        rows.append(dict(scene=s["id"], start_utc=s["start_utc"], pass_direction=s["pass_direction"],
                         relative_orbit=s["relative_orbit"], otsu_threshold_db=round(t, 3),
                         water_share_pct=round(100 * water.mean(), 3),
                         ref_water_cells_classified_water_pct=round(100 * water[inside].mean(), 2),
                         far_land_classified_water_pct=round(100 * np.mean(land < t), 2),
                         geoid_n_m=geoid_n, **meta))
        print(f"{tag}: Otsu {t:.2f} dB, water {100 * water.mean():.1f}% of grid, mapped water detected "
              f"{100 * water[inside].mean():.0f}%", flush=True)
    with open(os.path.join(OUT, "scenes_processed.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
