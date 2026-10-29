"""Finds and downloads the raw data for the Chalakudy experiment.

Every download is recorded in data/chalakudy/downloads.csv with its URL, the date it
was fetched, its size and SHA-256 checksum, so the raw files (kept out of git in
data/chalakudy/raw/) can be fetched again and checked.

Usage, from the repo root:
    python3 experiments/chalakudy_fetch.py gfd-events          # flood-database events, Jul-Sep 2018
    python3 experiments/chalakudy_fetch.py s1-scan 2018-07-01 2018-09-30
"""

import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import zipfile

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data", "chalakudy")
RAW = os.path.join(DATA, "raw")
DOWNLOADS = os.path.join(DATA, "downloads.csv")

S1_BUCKET = "https://sentinel-s1-l1c.s3.amazonaws.com"
GFD_BUCKET = "https://storage.googleapis.com/gfd_v1_4"

# Rough box around Chalakudy town, used only to decide which radar scenes to look at.
# The study-area boundary itself comes from map data (see chalakudy.py).
SEARCH_BOX = (76.25, 10.25, 76.40, 10.36)  # lon_min, lat_min, lon_max, lat_max


def session():
    """HTTP session that retries on connection resets and 5xx errors (the proxy drops some connections)."""
    s = requests.Session()
    retry = Retry(total=6, connect=6, read=6, backoff_factor=1.0, status_forcelist=(500, 502, 503, 504),
                  allowed_methods=("GET", "HEAD"))
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    return s


HTTP = session()


def record_download(url, path):
    """Appends url, date, size and SHA-256 of a downloaded file to downloads.csv."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    new = not os.path.exists(DOWNLOADS)
    with open(DOWNLOADS, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "url", "accessed_utc", "bytes", "sha256"])
        w.writerow([os.path.relpath(path, REPO), url, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    os.path.getsize(path), h.hexdigest()])


def download(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with HTTP.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(path + ".part", path)
    record_download(url, path)
    return path


# ---------------------------------------------------------------------------
# Global Flood Database: which events overlap Kerala in 2018?
# ---------------------------------------------------------------------------


class HttpFile(io.RawIOBase):
    """A read-only, seekable file over HTTP range requests (to read one member of a remote zip)."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        self.size = int(HTTP.head(url, timeout=30).headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size or len(b) == 0:
            return 0
        end = min(self.pos + len(b), self.size) - 1
        data = HTTP.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=60).content
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def gfd_events():
    listing = HTTP.get("https://storage.googleapis.com/storage/v1/b/gfd_v1_4/o?maxResults=2000", timeout=60).json()
    names = [o["name"] for o in listing["items"] if re.search(r"_From_2018(0[6-9])|_to_2018(0[7-9])", o["name"])]
    rows = []
    for name in sorted(names):
        z = zipfile.ZipFile(io.BufferedReader(HttpFile(f"{GFD_BUCKET}/{name}"), buffer_size=1 << 16))
        p = json.loads(z.read(next(m for m in z.namelist() if m.endswith("properties.json"))))
        rows.append(dict(file=name, dfo_id=p.get("id"), country=p.get("dfo_country"), began=p.get("began"),
                         ended=p.get("ended"), centroid_lat=p.get("dfo_centroid_y"),
                         centroid_lon=p.get("dfo_centroid_x"), countries=p.get("gfd_country_name")))
    out = os.path.join(DATA, "gfd_events_2018.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} events written to {os.path.relpath(out, REPO)}")


# ---------------------------------------------------------------------------
# Sentinel-1: which scenes cover Chalakudy?
# ---------------------------------------------------------------------------


def s3_list(prefix, delimiter="/"):
    keys, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix, "delimiter": delimiter, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        r = HTTP.get(S1_BUCKET + "/", params=params, timeout=60)
        r.raise_for_status()
        keys += re.findall(r"<Prefix>([^<]+)</Prefix>", r.text)[1:] if delimiter else re.findall(r"<Key>([^<]+)</Key>", r.text)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
        if not m:
            return keys
        token = m.group(1)


def point_in_polygon(x, y, poly):
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def covers_box(poly, box):
    x0, y0, x1, y1 = box
    return all(point_in_polygon(x, y, poly) for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def relative_orbit(mission, absolute):
    # ESA formulae for Sentinel-1A and 1B
    return (absolute - 73) % 175 + 1 if mission == "S1A" else (absolute - 27) % 175 + 1


def s1_scan(start, end):
    d0 = dt.date.fromisoformat(start)
    d1 = dt.date.fromisoformat(end)
    days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]

    def products(day):
        out = []
        for pol in ("DV", "SV", "DH", "SH"):
            prefix = f"GRD/{day.year}/{day.month}/{day.day}/IW/{pol}/"
            for p in s3_list(prefix):
                name = p.rstrip("/").split("/")[-1]
                hhmm = int(name.split("_")[4][9:13])  # start time, UTC
                # Kerala (76 E) is overflown around 00:40 UTC (descending) and 13:10 UTC (ascending)
                if 20 <= hhmm <= 130 or 1230 <= hhmm <= 1400:
                    out.append(p)
        return out

    def info(prefix):
        r = HTTP.get(f"{S1_BUCKET}/{prefix}productInfo.json", timeout=60)
        if r.status_code != 200:
            return None
        j = r.json()
        poly = j["footprint"]["coordinates"][0]
        if not covers_box(poly, SEARCH_BOX):
            return None
        mission = j["missionId"]
        hh = int(j["startTime"][11:13])
        return dict(id=j["id"], path=j["path"], start_utc=j["startTime"], mission=mission,
                    absolute_orbit=j["absoluteOrbitNumber"],
                    relative_orbit=relative_orbit(mission, j["absoluteOrbitNumber"]),
                    pass_direction="descending" if hh < 6 else "ascending", polarisation=j["polarization"],
                    footprint=json.dumps(poly))

    with cf.ThreadPoolExecutor(8) as ex:
        cands = [p for ps in ex.map(products, days) for p in ps]
        print(f"{len(cands)} candidate scenes at Kerala overpass times; checking footprints", flush=True)
        rows = [r for r in ex.map(info, cands) if r]
    rows.sort(key=lambda r: r["start_utc"])
    out = os.path.join(DATA, "sentinel1_scenes.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} scenes fully cover the search box; written to {os.path.relpath(out, REPO)}")
    for r in rows:
        print(r["start_utc"], r["mission"], "rel. orbit", r["relative_orbit"], r["pass_direction"], r["polarisation"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gfd-events":
        gfd_events()
    elif cmd == "s1-scan":
        s1_scan(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(f"unknown command {cmd}")
