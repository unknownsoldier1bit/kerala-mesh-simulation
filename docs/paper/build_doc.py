"""Builds the paper draft (IEEE-style layout) as Google Docs API requests, plus a Markdown copy.

The content lives here as blocks; numbers come from docs/paper/tables/*.csv,
data/chalakudy/data_summary.json and the analysis digests. Prose that is the authors' own
reasoning (mechanism, discussion, conclusion, related work) is left as highlighted placeholders.

    python3 docs/paper/build_doc.py text REVISION PART           # batch A, parts 1-3: replace the body
    python3 docs/paper/build_doc.py fix REVISION BODY_END        # body font (parts 1-2 clear it)
    python3 docs/paper/build_doc.py objects READ.json REVISION K  # batch B chunk K (0-5): tables, figures
    python3 docs/paper/build_doc.py markdown                      # docs/paper/paper.md

Each step's output is one update_doc call on the doc; read the doc before each step for its
revisionId. Batch B inserts bottom-up, so every chunk can use the positions of one read.

Outputs go to $OUT (default: the scratchpad given in OUT, else /tmp) as compact JSON.
"""
import csv
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLES = os.path.join(REPO, "docs", "paper", "tables")
OUT = os.environ.get("OUT", "/tmp")
DOC_ID = "1SNSzLxNARXC23C7tTHJGshCh_LWfS0TynoMmm9px1lE"
OLD_END = 23823
RAW = "https://raw.githubusercontent.com/unknownsoldier1bit/kerala-mesh-simulation/chalakudy-buildings/"
REPO_URL = "https://github.com/unknownsoldier1bit/kerala-mesh-simulation"
SHEET = "https://docs.google.com/spreadsheets/d/{}/edit"
SHEETS = {
    "main": "1gnS7UetEFGcwyK7lhuj4edeqys5bXc4nifLtvrYL8Vo",
    "sevload": "1OvHP_j3eGmIkZstZ1LRSvkOgCBW87-yEAFR78DBNI_A",
    "energy": "1Wp5mewH0bPBlpWY5MVTCVKXMlcE1R2Q0Yv1bona_9As",
    "kerala": "1ywzDpqOOb8zokcKIrl_vDLKEcnL7m_Xk0VVZnb78S4o",
    "cwin": "1EtVFyNQ9tS9Gz2DWX6KJ4PYZxXlIo1iBl9zZh_Ef-Wc",
    "csweep": "16s_cg-OsdJQps6Grn5XoNmkHVSolSnRZd-LFeL3Yx9Q",
}
FOLDER = "https://drive.google.com/drive/folders/1f4vcD4wOqkCFDs4JE8TINKguTIK8kZzK"

FONT = {"fontFamily": "Times New Roman"}
COL_GAP = 18      # pt between the two columns
WIDE = 500        # pt, width of a page-wide figure (text width is 522 pt)


def pt(x):
    return {"magnitude": x, "unit": "PT"}


def roman(n):
    out = ""
    for v, s in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


def read_csv(name):
    with open(os.path.join(TABLES, name), newline="") as f:
        return list(csv.reader(f))


ds = json.load(open(os.path.join(REPO, "data", "chalakudy", "data_summary.json")))

# ---------------------------------------------------------------- references (cite as [@key])
REFS = {
    "cag": 'Comptroller and Auditor General of India, Report No. 6 of 2021 (Kerala floods), ch. III and sec. 3.5.2. [Online]. Available: https://cag.gov.in/ag1/kerala/en/audit-report/details/114526',
    "tt": "TelecomTalk (reporting The Economic Times), report on the Telecom Secretary's review of network damage in Kerala, 27 Aug. 2018. [Online]. Available: https://telecomtalk.info/?p=180759 (press report).",
    "aodv": 'C. Perkins, E. Belding-Royer, and S. Das, "Ad hoc On-Demand Distance Vector (AODV) routing," RFC 3561, 2003. <hl>[VERIFY]</hl>',
    "olsr": 'T. Clausen and P. Jacquet, "Optimized Link State Routing Protocol (OLSR)," RFC 3626, 2003. <hl>[VERIFY]</hl>',
    "dsdv": 'C. E. Perkins and P. Bhagwat, "Highly dynamic destination-sequenced distance-vector routing (DSDV) for mobile computers," in Proc. ACM SIGCOMM, 1994. <hl>[VERIFY]</hl>',
    "ns3": "ns-3 network simulator, version 3.47. [Online]. Available: https://www.nsnam.org",
    "repo": f"Kerala mesh simulation: code, inputs, raw outputs and analysis. [Online]. Available: {REPO_URL} (branch chalakudy-buildings).",
    "kseb": "Kerala State Electricity Board, How KSEBL survived flood 2018. <hl>[NEEDS URL; check which area the 27 Aug date covers]</hl>",
    "overture": "Overture Maps Foundation, release 2026-10-21.0. [Online]. Available: https://overturemaps.org (accessed 29 Oct. 2026).",
    "osm": "OpenStreetMap contributors. [Online]. Available: https://www.openstreetmap.org (via Overture Maps).",
    "gob": 'W. Sirko et al., "Continental-scale building detection from high resolution satellite imagery," arXiv:2107.12283, 2021. <hl>[VERIFY]</hl>',
    "datameet": "DataMeet, Indian Village Boundaries: Kerala. [Online]. Available: https://github.com/datameet/indian_village_boundaries (accessed 29 Oct. 2026).",
    "dem": "European Space Agency, Copernicus DEM GLO-30, doi: 10.5270/ESA-c5d3d65. <hl>[VERIFY]</hl>",
    "s1": "European Space Agency, Copernicus Sentinel-1 GRD data, 2018 (AWS Open Data, sentinel-s1-l1c; accessed 29 Oct. 2026).",
    "otsu": 'N. Otsu, "A threshold selection method from gray-level histograms," IEEE Trans. Syst., Man, Cybern., vol. 9, no. 1, pp. 62-66, 1979. <hl>[VERIFY]</hl>',
    "dh": "Deccan Herald, article reporting that Chalakudy flooded early on 15 Aug. 2018. <hl>[NEEDS URL]</hl>",
    "scroll": "Scroll, article quoting a Member of Parliament that Chalakudy flooded on 17 Aug. 2018. <hl>[NEEDS URL]</hl>",
    "3gpp": '3GPP, "Study on evaluation methodology of new Vehicle-to-Everything (V2X) use cases for LTE and NR," TR 37.885 V15.3.0, Jun. 2019, Table 6.2.1-1. <hl>[VERIFY]</hl>',
    "friedman": 'M. Friedman, "The use of ranks to avoid the assumption of normality implicit in the analysis of variance," J. Amer. Statist. Assoc., vol. 32, no. 200, pp. 675-701, 1937. <hl>[VERIFY]</hl>',
    "wilcoxon": 'F. Wilcoxon, "Individual comparisons by ranking methods," Biometrics Bull., vol. 1, no. 6, pp. 80-83, 1945. <hl>[VERIFY]</hl>',
    "holm": 'S. Holm, "A simple sequentially rejective multiple test procedure," Scand. J. Statist., vol. 6, no. 2, pp. 65-70, 1979. <hl>[VERIFY]</hl>',
    "memo": "Government of Kerala, Additional Memorandum, 13 Sep. 2018, Table 3, pp. 11-12. [Online]. Available: https://recovery.preventionweb.net/media/101476/download",
}

# ---------------------------------------------------------------- tables
# key -> (caption, rows incl. header, column widths in pt, header row count)
T = {}
T["timers"] = ("Default protocol timers in ns-3.47, used unchanged in every run", [
    ["Protocol", "Setting", "Value"],
    ["OLSR", "HELLO interval / neighbour hold time", "2 s / 6 s"],
    ["OLSR", "TC interval", "5 s"],
    ["AODV", "HELLO interval / allowed HELLO loss", "1 s / 2"],
    ["AODV", "Active route timeout", "3 s"],
    ["AODV", "RREQ retries", "2"],
    ["DSDV", "Periodic update / settling time", "15 s / 5 s"],
    ["DSDV", "Route dropped after", "45 s without update"],
    ["AODV", "Link-break detection", "MAC retry limit; missed HELLOs"],
    ["OLSR", "Link-break detection", "no HELLO for 6 s"],
], [44, 130, 78])
T["config"] = ("Simulation configuration", [
    ["Item", "Setting"],
    ["Simulator", "ns-3.47, optimized build"],
    ["Protocols", "AODV, OLSR, DSDV with ns-3 default parameters"],
    ["Radio and MAC", "IEEE 802.11b ad hoc; data 11 Mbps, control frames and broadcasts 1 Mbps; 16.02 dBm transmit power; RTS/CTS off; ARP tables pre-filled"],
    ["Radio range", "150 m unit disk (assumed; a cited path-loss model is a sensitivity run)"],
    ["Topologies", "Main grid: 25, 50 or 100 nodes at random in a 500 m square, redrawn until connected. Chalakudy: 100 devices at real building positions in a 1 km square"],
    ["Mobility", "None (static nodes)"],
    ["Traffic", "UDP, 512-byte payload. Main grid: 10 constant-rate flows, 4 packets/s, 60-290 s. Flood scenarios: 20 flows of bursts (5 packets 0.2 s apart, exponential gaps, mean 15 s), 60-448 s"],
    ["Duration", "300 s (main grid, severity, load); 600 s (energy); 450 s (flood scenarios); 60 s warm-up without traffic"],
    ["Repetitions", "Seeds 1-10 per configuration, paired across protocols"],
], [64, 188])
T["experiments"] = ("Experiments and number of runs", [
    ["Experiment", "What varies", "Runs"],
    ["main", "3 protocols x 6 scenarios x 25/50/100 nodes", "540"],
    ["severity", "5-30% of random relay nodes or links fail; 50 nodes", "240"],
    ["load", "5/10/20 flows; baseline or node failure; 50 nodes", "180"],
    ["energy", "2 radio profiles; batteries run out; 50 nodes", "60"],
    ["kerala", "Kerala-anchored model, 5 failure models; 50 nodes", "150"],
    ["kerala100", "the same with 100 nodes", "150"],
    ["rtscts100", "100-node baseline with RTS/CTS on", "30"],
    ["chalakudy", "3 failure models; onset 15 or 17 Aug; batteries unlimited or limited", "360"],
    ["chalakudy_prop", "cited path-loss model instead of the 150 m disk", "90"],
    ["chalakudy_share", "10% and 50% of devices flooded", "120"],
    ["chalakudy_battery", "25% and 100% of the battery for the radio", "180"],
    ["chalakudy_traffic", "mean gap between bursts 7.5 s and 30 s", "180"],
    ["chalakudy_check", "cross-checks (FlowMonitor, ns-3 energy framework); 50 devices, seeds 1-2", "36"],
    ["Total", "", "2,316"],
], [78, 146, 28])
T["scenarios"] = ("Failure scenarios of the main grid", [
    ["Scenario", "What fails", "When", "Selection"],
    ["Baseline", "nothing", "-", "-"],
    ["Link failure", "the 5 links carrying the most traffic", "120 s, permanent", "deterministic"],
    ["Node failure", "the busiest 10% of relays", "120 s, permanent", "deterministic"],
    ["Multiple failures", "3 waves of 5% of relays and 5% of links", "120, 135, 150 s", "random (seeded)"],
    ["Partition", "every link crossing the vertical midline", "120-210 s, then restored", "deterministic"],
    ["Recovery", "the same relays as node failure", "120-210 s, then restored", "deterministic"],
], [54, 92, 58, 48])
m, sq, s1 = ds["municipality"], ds["study_square"], ds["sentinel1"]
T["data"] = ("Real data used in the Chalakudy scenario", [
    ["Item", "Source", "Value used", "Kind"],
    ["Municipality boundary", "DataMeet Indian Village Boundaries (ODbL)", f"Chalakudy, Thrissur district, {m['area_km2']} km²", "Measured"],
    ["Buildings", "Overture Maps 2026-10-21.0 (Google Open Buildings, OpenStreetMap)",
     f"{m['buildings']:,} in the municipality ({m['buildings_by_source']['Google Open Buildings']:,} Google, {m['buildings_by_source']['OpenStreetMap']:,} OSM); median footprint {m['footprint_m2']['p50']:.0f} m²", "Measured"],
    ["Study square", "rule applied to the data", f"1 km x 1 km with the most buildings among the town's lowest 25%; {sq['buildings']:,} buildings", "Derived (rule assumed)"],
    ["Ground height", "Copernicus DEM GLO-30 (surface model)", f"5th percentile within 50 m of each building; square median {sq['ground_estimate_m']['p50']:.1f} m (10th-90th percentile {sq['ground_estimate_m']['p10']:.1f}-{sq['ground_estimate_m']['p90']:.1f} m)", "Derived"],
    ["Water on 24 dates", "Sentinel-1 IW GRDH, Jan-Sep 2018", f"{s1['scenes']} scenes; no image between 9 and 21 Aug; thresholds {s1['threshold_db_range'][0]:.1f} to {s1['threshold_db_range'][1]:.1f} dB", "Measured / derived"],
    ["Flood water in the municipality", "radar maps", "0.98 km² on 9 and 21 Aug; 0.25 km² on 27 Aug", "Derived"],
    ["Nearest flood water to a building in the square", "radar maps", f"{sq['distance_to_radar_flood_water']['2018-08-21_des']['nearest_m']:.0f} m (21 Aug); none within 20 m on any date; 2 buildings within 50 m on 9 Aug", "Derived"],
    ["Devices", "random buildings, seeds 1-10", "100 per run; 7.2 neighbours on average; 97% in the largest connected group", "Assumed (positions measured)"],
], [104, 140, 206, 72])

r = read_csv("main_within_1s.csv")
T["main"] = ("Delivered within T = 1 s (%) in the main grid, mean ± 95% CI over 10 seeds", r, [72, 30, 50, 50, 50])


def first(name):
    return {row[0]: row[1:] for row in read_csv(name)[1:]}


pdr, dly, ctl = first("main_baseline_pdr.csv"), first("main_baseline_delay_median.csv"), first("main_baseline_control.csv")
rows = [["Metric", "Nodes", "AODV", "OLSR", "DSDV"]]
for lab, d in (("PDR (%)", pdr), ("Median delay (ms)", dly), ("Control pkts/node/s", ctl)):
    for n in ("25", "50", "100"):
        rows.append([lab, n] + d[n])
rows.append(["MAC link breaks/run", "100", "14,943", "2.4", "138.5"])
T["baseline"] = ("Baseline scenario of the main grid: delivery, delay and control traffic (mean ± 95% CI)", rows, [76, 28, 52, 48, 48])
T["severity"] = ("Delivered within 1 s (%) under random failures, 50 nodes", read_csv("severity_within_1s.csv"), [64, 38, 50, 50, 50])
T["load"] = ("Delivered within 1 s (%) by number of flows, 50 nodes", read_csv("load_within_1s.csv"), [64, 38, 50, 50, 50])
e = read_csv("energy.csv")
T["energy"] = ("Energy experiment, 50 nodes: time until nodes run flat and control traffic", [
    ["Radio", "Protocol", "First node flat (s)", "Half of nodes flat (s)", "Control pkts/node/s"]] +
    [[row[0].replace("ns-3 default radio", "Default"), row[1], row[2], row[3], row[4]] for row in e[1:]], [50, 40, 54, 54, 54])
for ph, lab in (("acute", "acute phase, 14-18 Aug"), ("sustained", "sustained phase, 18-27 Aug")):
    k = read_csv(f"kerala_{ph}_within_1s.csv")
    T[f"kerala_{ph}"] = (f"Kerala-anchored scenario, {lab}: delivered within 1 s (%)", k, [30, 72, 50, 50, 50])
c = read_csv("chalakudy_main_within_1s.csv")
WIN = {"14-15 Aug (before onset), all sent": "Before onset", "15-18 Aug (acute), all sent": "Acute",
       "15-18 Aug (acute), path existed": "Acute, path existed", "18-27 Aug (sustained), all sent": "Sustained",
       "18-27 Aug (sustained), path existed": "Sustained, path existed"}
SC = {"No flooding": "No flooding", "Flood (lowest ground first)": "Flood order", "Uniform random": "Uniform random"}
rows, seen = [["Window", "Scenario", "AODV", "OLSR", "DSDV"]], set()
for row in c[1:]:
    w = WIN[row[1]]
    if w == "Before onset":
        if w in seen:
            continue
        seen.add(w)
        rows.append([w, "all", *row[2:]])
    else:
        rows.append([w, SC[row[0]], *row[2:]])
T["chalakudy"] = ("Chalakudy scenario, onset 15 Aug, 25% flooded, no battery limit: delivered within 1 s (%)", rows, [58, 46, 49, 49, 50])
sw = read_csv("chalakudy_sweeps_acute_within_1s.csv")
rows = [["Setting", "Failures", "AODV", "OLSR", "DSDV"]]
for model in ("Flood (lowest ground first)", "Uniform random"):
    for row in sw[1:]:
        if row[2] != model:
            continue
        if row[0].startswith("Flooded"):
            lab = f"{row[1]}% flooded" + (" (main)" if row[1] == "25" else "")
        else:
            if row[1] == "15":
                continue
            lab = f"gap {row[1]} s"
        rows.append([lab, SC[model].replace("Uniform random", "Uniform"), *row[3:]])
T["sweeps"] = ("Chalakudy, acute phase, onset 15 Aug, no battery limit: delivered within 1 s (%) as one setting changes (main: 25% flooded, 15 s gap)", rows, [68, 44, 47, 47, 46])
T["params"] = ("Chalakudy parameters: measured, derived or assumed (condensed from data/chalakudy/PROVENANCE.md)", [
    ["Parameter", "Value", "Kind", "Swept"],
    ["Study area", "1 km square, lowest-lying built-up area", "Assumed rule", "alternative square recorded"],
    ["Devices", "100, one per random building", "Assumed", "network structure only (50-1,000)"],
    ["Ground estimate", "5th percentile of DEM within 50 m", "Derived", "-"],
    ["Flooded share at peak", "25%", "Assumed", "10%, 25%, 50%"],
    ["Onset", "15 Aug (sources disagree)", "Measured (press)", "15, 17 Aug"],
    ["Peak", "18 Aug 00:00", "Assumed from dated events", "-"],
    ["Flooded devices return", "no", "Assumed", "-"],
    ["Power cut", "00:00 on the onset day", "Assumed (KSEB date not found)", "-"],
    ["Power back / end of run", "27 Aug", "Measured (KSEB, NEEDS URL)", "-"],
    ["Battery", "3,000 mAh, 3.85 V (placeholder)", "Assumed", "-"],
    ["Battery share for the radio", "50%", "Assumed", "25%, 50%, 100%"],
    ["Charge at the power cut", "uniform 20-100%", "Assumed", "-"],
    ["Radio energy model", "ns-3 defaults (0.82 W idle)", "Assumed (values from ns-3)", "-"],
    ["Time compression", "1 day = 30 s", "Assumed", "-"],
    ["Traffic", "20 flows, bursts of 5 packets, mean gap 15 s", "Assumed", "7.5, 15, 30 s"],
    ["Radio range", "150 m unit disk", "Assumed", "cited path-loss model (62.8 m)"],
    ["Geoid offset", "-96 m (EGM2008 check: -95.7 m)", "Derived", "-"],
    ["Water threshold", "Otsu per scene, -12.9 to -10.6 dB", "Derived", "-"],
    ["Minimum flood patch", "10 cells (0.1 ha)", "Assumed", "-"],
], [124, 170, 118, 110])
rows = [["Date (2018)", "Time (UTC)", "Satellite", "Pass, orbit", "Threshold (dB)", "Water (%)", "Reference water detected (%)", "Far land as water (%)"]]
for s in s1["per_scene"]:
    rows.append([s["date"][5:].replace("-", "/"), s["time_utc"], s["mission"], f"{s['pass_direction']} {s['relative_orbit']}",
                 f"{s['threshold_db']:.1f}", f"{s['water_share_pct']:.1f}", f"{s['reference_water_detected_pct']:.1f}",
                 f"{s['far_land_detected_as_water_pct']:.2f}"])
T["scenes"] = ("Sentinel-1 scenes over Chalakudy (dates as month/day)", rows, [52, 50, 50, 84, 64, 52, 85, 85])
T["timeline"] = ("Dated 2018 events used by the flood scenarios", [
    ["Date (2018)", "Event", "Used as", "Source"],
    ["14-18 Aug", "Dam releases (Idukki shutters opened 10 Aug)", "Water rises until 18 Aug 00:00", "CAG Report No. 6 of 2021, ch. III [@cag]"],
    ["15-17 Aug", "IMD red alert for heavy rain, Thrissur", "Same", "Kerala Additional Memorandum, Table 3 [@memo]"],
    ["15 or 17 Aug", "Chalakudy floods", "Onset (both are run)", "Deccan Herald [@dh]; Scroll [@scroll]"],
    ["16 Aug", "Communications fail in Chalakudy and Idukki taluks", "Context", "CAG sec. 3.5.2 [@cag]"],
    ["27 Aug", "Last Thrissur substation back on", "End of run", "KSEB [@kseb]"],
], [70, 190, 110, 152])

FIGS = {
    "study": ("results/analysis_chalakudy/figures/chalakudy_study_area.png", 240, 1293, 1317,
              "Chalakudy study square (1 km, black outline) with the 100 devices of seed 1 in the flood scenario with 25% lost. Real: building positions, radar water and the ground-height order. Assumed: which buildings have devices, and the 25% share. © OpenStreetMap contributors, Overture Maps Foundation; contains modified Copernicus Sentinel data 2018."),
    "density": ("results/analysis_chalakudy/figures/chalakudy_network_density.png", WIDE, 1783, 701,
                "Network structure on the Chalakudy buildings (no simulation): mean neighbours per device and share of devices in the largest connected group, against device density, at 150 m and at the 62.8 m range of the cited path-loss model. Squares: the main grid. Mean of seeds 1-10."),
    "main": ("results/analysis/figures/main_within_1s.png", WIDE, 2143, 762,
             "Delivered within T = 1 s in the main grid, by failure scenario and network size. Bars: mean over seeds 1-10; error bars: 95% confidence interval."),
    "energy": ("results/analysis/figures/energy_lifetime.png", WIDE, 2183, 703,
               "Energy experiment (50 nodes): simulation time until the first node, 10% of nodes and 50% of nodes run flat, with ns-3's default radio and a low-idle radio. Error bars: 95% confidence interval."),
    "k50": ("results/analysis/figures/kerala_within_T_by_phase_n50.png", 380, 1783, 1322,
            "Kerala-anchored scenario, 50 nodes: delivered within 1 s in the acute (14-18 Aug) and sustained (18-27 Aug) phases, for all sent packets (top) and for packets sent while a path existed (bottom). A hypothetical, time-compressed scenario anchored to dated 2018 events, not measured Kerala data."),
    "k100": ("results/analysis/figures/kerala_within_T_by_phase_n100.png", 380, 1783, 1322,
             "Kerala-anchored scenario, 100 nodes, as in Fig. 5."),
    "cwin": ("results/analysis_chalakudy/figures/chalakudy_within_T_by_window.png", WIDE, 2125, 1357,
             "Chalakudy scenario: delivered within 1 s by window, onset 15 Aug (top) or 17 Aug (bottom), 25% flooded, no battery limit. Real data: building positions, ground height, Sentinel-1 water, event dates. Assumed: devices per building, flooded share, power cut, batteries, traffic, 150 m range, 1 day = 30 s."),
    "cconn": ("results/analysis_chalakudy/figures/chalakudy_connected_within_T_by_window.png", WIDE, 2087, 1357,
              "Chalakudy scenario as in Fig. 7, counting only packets sent while a path existed between source and destination."),
    "ctime": ("results/analysis_chalakudy/figures/chalakudy_over_time_on15_nobatt.png", WIDE, 2179, 1197,
              "Chalakudy scenario over time, onset 15 Aug, no battery limit: devices still running (top) and delivered within 1 s in 10 s bins pooled over seeds 1-10 (bottom). Dashed line: 15 Aug; solid line: 18 Aug."),
    "csens": ("results/analysis_chalakudy/figures/chalakudy_sensitivity_acute.png", WIDE, 2126, 1307,
              "Chalakudy, acute phase, onset 15 Aug: delivered within 1 s as one setting changes from the main setting (25% flooded, 15 s gap, 50% battery share). Flooded share and traffic: no battery limit; battery share: batteries limited. All swept values are assumptions."),
    "qa": ("results/analysis_chalakudy/figures/chalakudy_qa_geolocation.png", 300, 1211, 1317,
           "Geolocation check of the radar maps: permanent water and flood water still visible on 21 Aug against the municipality boundary (DataMeet) and the study square. The river on the radar maps follows the municipality's southern boundary. Contains modified Copernicus Sentinel data 2018."),
}

# ---------------------------------------------------------------- the paper, as blocks
B = []


def add(kind, text="", **kw):
    B.append(dict(kind=kind, text=text, **kw))


TN, FN = {}, {}


def table(key, wide=False, **kw):
    TN[key] = len(TN) + 1
    add("tcap", f"TABLE {roman(TN[key])}: {T[key][0]}", table=key, wide=wide, **kw)


def fig(key):
    FN[key] = len(FN) + 1
    add("fig", "{{F:" + key + "}}", figure=key)
    add("fcap", f"Fig. {FN[key]}: {FIGS[key][4]}")


def ph(text):
    add("p", f"<hl>[{text}]</hl>")


add("title", "AODV Versus OLSR Under Time-Evolving Flood Failures: A Simulation Study Anchored to the 2018 Kerala Floods")
add("authors", "Saksham Bhatia and <hl>[co-author]</hl>")
add("affil", "<hl>[School, city, country; email]</hl>")
add("abstract", "<i>Abstract</i>—When floods cut mains power and cellular service, mesh nodes that relay messages for each other over ad hoc Wi-Fi can keep messages moving. We compare three routing protocols, AODV, OLSR and DSDV, in the ns-3.47 simulator under node failures that evolve over time and are anchored to dated events of the August 2018 Kerala floods. The primary metric is the fraction of messages delivered within a deadline T, with T = 1 s as a placeholder. We ran 1,350 simulations of abstract failure scenarios, failure severity, traffic load, battery depletion and a Kerala-anchored scenario on synthetic terrain, and 966 simulations of a scenario built on real building positions, ground heights and Sentinel-1 radar water maps of Chalakudy, Thrissur district. Without flooding or battery depletion, OLSR delivered 99.7-100% of messages within 1 s in every network tested, while AODV fell to 59.4% at 100 nodes in a 500 m square and delivered 86-91% on the Chalakudy building topology. With 25% of devices flooded in Chalakudy, delivery within 1 s fell to 66-76% for all three protocols in the acute phase (onset 15 Aug), and failures ordered by real ground height gave the same delivery as failures at random devices. With the assumed batteries, every device ran flat within hours of the power cut under every protocol, so the sustained-phase half of the premise could not be tested. <hl>[Your concluding sentence: what these results mean for the premise.]</hl>", sb=2)
add("index", "<i>Index Terms</i>—Mobile ad hoc networks, AODV, OLSR, DSDV, ns-3, disaster communication, node failure, floods, Kerala 2018.")

add("h1", "I. Introduction")
add("p", "In August 2018 heavy rain and dam releases flooded large parts of Kerala, India, and communications failed across the affected districts. The Comptroller and Auditor General of India records a total failure of communications in Chalakudy and Idukki taluks [@cag], and a press report of the Telecom Secretary's review put about 27% of the state's mobile base stations out of service [@tt]. When the cellular network and mains power fail, mobile devices can still pass messages to each other if they form a mesh network, in which each device relays messages for the others. How quickly messages then arrive depends in part on the routing protocol.")
add("p", "Routing protocols for such mobile ad hoc networks fall into two families. Reactive protocols such as AODV [@aodv] find a route only when a message needs one. Proactive protocols such as OLSR [@olsr] and DSDV [@dsdv] keep a route to every destination at all times by exchanging control messages periodically. Comparisons of AODV and OLSR are common. The contribution of this paper is the failure model: node failures that evolve over time and are anchored to dated events of the 2018 Kerala floods, including a scenario built on real building positions, ground heights and radar water maps of the town of Chalakudy, with every input labelled as measured, derived or assumed.")
add("p", "The premise tested, in the first author's words, is:")
add("quote", "During the acute phase of a flood such as Kerala 2018, OLSR delivers a higher fraction of messages within a fixed deadline than AODV. OLSR keeps routes computed in advance, so a message can leave immediately. AODV has to discover a route first, and again after every link break. With frequent breaks and short bursts of traffic, that discovery delay uses up much of the deadline. The advantage has a cost: OLSR's periodic control traffic drains batteries faster. So over the sustained phase, as nodes run out of power, AODV should close the gap or overtake it.")
add("p", "We test this premise in simulation with the ns-3.47 network simulator [@ns3]. Section II describes the three protocols and Section III the mechanism behind the premise. Section IV describes the simulations and the two flood scenarios, Section V reports the results, and Sections VI and VII discuss them and their limitations.")
ph("Your text: the research question(s), why a deadline matters for disaster messages, and whether DSDV stays in the paper (it was included because the project's deliverables asked for it).")

add("h1", "II. Background")
add("h2", "A. AODV")
add("p", "Ad hoc On-Demand Distance Vector routing (AODV) [@aodv] is reactive. When a node has a packet for a destination it has no route to, it broadcasts a route request (RREQ) that spreads through the network; the destination, or a node with a fresh enough route, answers with a route reply (RREP) along the reverse path. Packets wait in a buffer until the reply arrives. Routes that are not used expire, and a broken link triggers a route error (RERR) and, at the source, a new discovery. Sequence numbers issued by destinations prevent routing loops.")
add("h2", "B. OLSR")
add("p", "Optimized Link State Routing (OLSR) [@olsr] is proactive. Every node sends HELLO messages to discover its neighbours and selects some of them as multipoint relays (MPRs); only MPRs forward the topology control (TC) messages that spread link-state information through the network. Each node computes a shortest-path route to every destination in advance, so a packet can leave as soon as it is generated. The cost is control traffic sent periodically, whether or not there is data to send.")
add("h2", "C. DSDV")
add("p", "Destination-Sequenced Distance-Vector routing (DSDV) [@dsdv] is a proactive distance-vector protocol: each node periodically advertises its routing table to its neighbours, and sequence numbers issued by destinations keep the routes loop-free. Table I lists the timers of the ns-3.47 implementations of the three protocols.")
table("timers")
add("h2", "D. Related Work")
ph("Your text: related work. No related-work papers were read or verified in this project; cite only papers you have opened yourself.")

add("h1", "III. Mechanism")
ph("Your mechanism paragraph (step 2 of the plan; you write this). Why should OLSR deliver more messages within T in the acute phase, and why should AODV close the gap in the sustained phase?")

add("h1", "IV. Methods")
add("h2", "A. Simulator and Network")
add("p", "All simulations use ns-3.47 [@ns3] with its implementations of AODV, OLSR and DSDV at their default settings (Table I). Devices are static and use IEEE 802.11b in ad hoc mode. Radio propagation is a unit disk: a frame is received within 150 m and lost beyond it. This range is an assumption; Section IV-H replaces it with a published path-loss model. Table II summarises the configuration; the exact settings of every run are stored with its output [@repo].")
table("config")
add("h2", "B. Metrics")
add("p", "The primary metric is the fraction of messages delivered within a deadline T: a message counts only if it reaches its destination no later than T after it was sent. T = 1 s is a placeholder until it is set from Kerala data; results for T = 0.5, 2 and 5 s are in the data files. We also report the packet delivery ratio (PDR), the median end-to-end delay, and the routing control packets sent per node per second. In the flood scenarios we add a connectivity control: delivery within T counted only over packets sent while the working devices still had a path from source to destination. Losses that remain in this measure are caused by routing, not by the network being cut.")
add("h2", "C. Experiments")
add("p", "Table III lists the experiments. Each configuration was run with seeds 1-10. Runs are paired: for a given seed, every protocol sees the same topology, traffic and failures. All 2,316 runs finished without errors.")
table("experiments")
add("h2", "D. Abstract Failure Scenarios")
add("p", "In the main grid, 25, 50 or 100 nodes are placed at random in a 500 m square (100, 200 and 400 nodes per km²; 5.2, 10.5 and 22.4 neighbours on average), and placements are redrawn until the network is connected. Ten flows each send 4 packets per second from 60 to 290 s. Table IV lists the six failure scenarios. Two sweeps use 50 nodes: the severity sweep fails 5-30% of random relay nodes or links, and the load sweep runs 5, 10 or 20 flows. In the energy experiment every node starts with a random battery that, idling only, would last 200-600 s; nothing recharges, and a radio switches off at 10% charge, as in ns-3's BasicEnergySource. It is run with ns-3's default radio currents, where an idle radio draws almost as much as a receiving one (0.273 A against 0.313 A), and with a hypothetical low-idle radio that draws ns-3's sleep current (0.033 A) when idle, so that energy depends mainly on sending and receiving.")
table("scenarios")
add("h2", "E. Kerala-Anchored Failure Model")
add("p", "The Kerala-anchored model places 50 or 100 nodes in the 500 m square on synthetic terrain and times their failures by dated events of 2018 (Appendix C). One day is compressed into 30 simulated seconds (a factor of 2,880): 14 Aug 00:00 falls at 60 s, and the run ends on 27 Aug, when the last Thrissur substation was switched back on [@kseb]. In the acute phase, 14-18 Aug, nodes fail as the water rises, following an assumed curve: 0, 15, 60, 90 and 100% of the eventual flood failures by 14, 15, 16, 17 and 18 Aug. Either 27% of nodes flood, the press-reported statewide base-station outage [@tt] used as a floor, or 50%, a hypothetical value. The terrain has a river along the west edge and ground rising eastward with random noise, and the lowest nodes fail first. A uniform-random baseline fails the same number of nodes at the same times, and a no-flood control has no flood failures. In the sustained phase, 18-27 Aug, nothing recharges: each battery would last, idling only, until a random date between 19 Aug and 6 Sep. Traffic is 20 flows of bursts (5 packets 0.2 s apart, exponential gaps with a mean of 15 s). Only failures and batteries are time-compressed; routing timers and packets run at real speed. Positions, terrain and the flood curve are synthetic or assumed, so this is a hypothetical scenario anchored to dated events, not measured Kerala data.")
add("h2", "F. Chalakudy Scenario: Data")
add("p", "The second flood scenario uses real data for Chalakudy municipality, in the Chalakudy taluk of Thrissur district, where the CAG records a total failure of communications in 2018 [@cag]. Table V lists the inputs. Building footprints come from Overture Maps [@overture], which combines OpenStreetMap [@osm] and Google Open Buildings [@gob]; the municipality boundary comes from DataMeet [@datameet]; ground height from the Copernicus GLO-30 surface model [@dem]; and water extent on 24 dates in 2018 from Sentinel-1 radar [@s1], classified with Otsu's threshold for each scene [@otsu]. The study area is the 1 km square with the most buildings among the town's lowest-lying 25% (1,383 buildings; Fig. 1). Each run places 100 devices at the centroids of randomly chosen buildings; at 150 m they have 7.2 neighbours on average, and 97% of them are in the largest connected group (Fig. 2). Every input is labelled measured, derived or assumed; Appendix A condenses that record.")
add("p", "Radar cannot see water among buildings and trees, and there is no image between 9 and 21 Aug, so the maps miss the flood peak. No building in the square lies within 20 m of radar-visible flood water on any date (two lie within 50 m, on 9 Aug only). The radar therefore shows when the fields around this part of town flooded and when the water receded, but not which buildings flooded, and the failure order in the square is set by ground height alone.", sb_after=1)
table("data", wide=True)
fig("study")
fig("density")
add("h2", "G. Chalakudy Scenario: Failures, Batteries and Traffic", sb=2)
add("p", "Each seed compares three failure models on the same devices and flows. In the flood-order model, 25% of devices fail (10% and 50% in a sweep), evenly spaced in time from the onset day to 18 Aug 00:00, lowest ground first; flooded devices do not return. Press reports disagree on the onset, 15 Aug [@dh] or 17 Aug [@scroll], so both are run. The uniform-random model fails the same number of devices at the same times at random devices, and the no-flood control has no failures. The flood pattern is only moderately clustered: the nearest other failed device is 83 m away on average under the flood order and about 104 m under random failures.")
add("p", "Batteries are either unlimited, which isolates the effect of flooding, or limited. From the power cut, assumed at 00:00 on the onset day, each device has a random charge of 20-100% of an assumed 3,000 mAh, 3.85 V battery, of which 50% is available to the radio (25% and 100% in a sweep), time-compressed like the scenario; radio power uses ns-3's default currents. Traffic is 20 flows between devices of the same connected group at least two hops apart, sending bursts of 5 packets 0.2 s apart with exponential gaps (mean 15 s; 7.5 s and 30 s in a sweep). One day lasts 30 s, as in the Kerala-anchored model. Results are reported for three windows: before the onset, the acute phase (onset to 18 Aug) and the sustained phase (18-27 Aug).")
add("h2", "H. Propagation Sensitivity")
add("p", "To test the 150 m assumption, the chalakudy_prop experiment replaces the unit disk with the 3GPP TR 37.885 urban non-line-of-sight path-loss formula, PL = 36.85 + 30 log10(d) + 18.9 log10(f) [@3gpp], with f = 2.412 GHz, as implemented in ns-3.47 and without adjustment. With ns-3's default transmit power (16.02 dBm) and preamble-detection threshold (-82 dBm), frames get through up to 62.8 m (checked with two devices: all frames at 62.5 m, none at 63 m). The model assumes no line of sight on every link, and it was made for vehicles, not for devices inside houses.")
add("h2", "I. Statistics")
add("p", "Results are means over the 10 seeds with 95% confidence intervals (t-distribution). Because runs are paired, protocols are compared with a Friedman test over the three protocols [@friedman], followed by two-sided Wilcoxon signed-rank tests for each pair [@wilcoxon] with Holm's correction over the three pairs [@holm]. Flood-order and uniform-random failures are compared with Wilcoxon tests for each protocol, Holm-corrected over the protocols. With 10 paired seeds the smallest possible Holm-corrected p value is 0.0059. The correction covers only the comparisons within one configuration and metric; across the hundreds of tests in this paper some p values below 0.05 are expected by chance, so a difference carries weight only when it holds across configurations.")
add("h2", "J. Validation")
add("p", "A four-node diamond topology was simulated first as a sanity check. Our packet tracker agrees exactly with ns-3's FlowMonitor in the Chalakudy cross-check runs, and our state-based energy count agrees with ns-3's energy framework when batteries are effectively unlimited. ns-3's energy framework did not drain finite batteries correctly (its radio model stopped counting at about 72% of the initial energy), so all battery-limited runs use the state-based model. At 100 or more nodes some OLSR packets exceeded the Wi-Fi MTU and were fragmented, which crashed or slightly miscounted the control-traffic counter; the counter was fixed and the 29 affected runs were redone. Every run's metrics recompute identically from its raw files, and the analysis reproduces byte for byte. On a second machine 467 of 482 replayed runs matched exactly; the other 15, all dense 100-node AODV runs, differ run by run but agree on average.")

add("h1", "V. Results")
add("h2", "A. Main Grid")
add("p", "Table VI and Fig. 3 give delivery within 1 s in the main grid. At 100 nodes AODV delivers 24-41 points less than OLSR in every scenario (59.4% against 99.9% in the baseline; Holm p = 0.0059 in all six scenarios), while DSDV stays within 3 points of OLSR. At 25 nodes AODV is slightly ahead of OLSR in the five failure scenarios (median paired difference 0.5-1.7 points, Holm p ≤ 0.016), and at 50 nodes AODV and OLSR differ by at most 1.1 points. The partition caps every protocol at 73-76% at 25 and 50 nodes, since packets between the two halves cannot be delivered while it lasts.")
table("main")
add("p", "Table VII shows what changes at 100 nodes in the baseline. AODV's PDR falls to 60.0%, its median delay rises to 17.5 ms against 2.1 ms for OLSR, and it sends 18.65 control packets per node per second against 0.75 for OLSR. The MAC reports 14,943 link breaks (unicast frames dropped after the retry limit) per AODV run, against 2.4 for OLSR and 138.5 for DSDV, and AODV's median route discovery takes 77.6 ms. With RTS/CTS switched on, AODV delivers 46.7% within 1 s, OLSR 99.9% and DSDV 97.1%.")
table("baseline", sb_after=1)
fig("main")
add("h2", "B. Severity and Load", sb=2)
add("p", "Random failures of 5-30% of relay nodes or links at 50 nodes leave every protocol at 98.2-99.9% delivery within 1 s (Table VIII). With more flows, AODV's delivery within 1 s in the baseline falls from 99.7% with 5 flows to 96.2% with 20, while OLSR stays at 100.0% and DSDV at 99.4-99.5% (Table IX).")
table("severity")
table("load")
add("h2", "C. Energy")
add("p", "With ns-3's default radio the first node runs flat at about 205 s and half of the nodes at about 400 s under every protocol (Table X, Fig. 4), with no significant difference between protocols in the time of the first depletion. OLSR sends the fewest control packets (0.49 per node per second, against 1.75 for AODV and 1.86 for DSDV). With the low-idle radio the first node runs flat at 165.2 s under AODV, 157.8 s under OLSR and 154.4 s under DSDV (paired medians: AODV later than OLSR by 6 s, Holm p = 0.012; OLSR later than DSDV by 4 s, p = 0.043).")
table("energy", sb_after=1)
fig("energy")
add("h2", "D. Kerala-Anchored Scenario", sb=2)
add("p", "Tables XI and XII and Figs. 5 and 6 give delivery within 1 s in the two phases. Without flooding OLSR already delivers more than AODV in the acute phase: 99.9% against 96.4% at 50 nodes and 100.0% against 76.0% at 100 nodes. At 100 nodes OLSR stays ahead of AODV in every flood scenario of the acute phase, by 8.5-15.7 points (Holm p = 0.0059 in each), a smaller gap than in the no-flood control (24.0 points). At 50 nodes the flood scenarios bring all three protocols to 69-88%, and AODV and OLSR differ by at most 1.8 points: OLSR is ahead under Kerala-anchored 27% failures (median 1.3 points, p = 0.029) and AODV under random 50% failures (1.2 points, p = 0.037). Counting only packets sent while a path existed, OLSR delivers 94.5-99.5% in the acute phase at 100 nodes and AODV 80.2-82.9%.")
table("kerala_acute")
add("p", "In the sustained phase, with the flooded nodes gone and batteries running out, delivery within 1 s in the flood scenarios is 26-58% at 50 nodes and 33-60% at 100 nodes. At 50 nodes AODV and OLSR do not differ significantly in any scenario. At 100 nodes OLSR stays ahead in four of the five scenarios (median 1.6-10.6 points, Holm p ≤ 0.012); under random 50% failures the 1.2-point difference is not significant.")
table("kerala_sustained", sb_after=1)
fig("k50")
fig("k100")
add("h2", "E. Chalakudy Scenario", sb=2)
add("p", "Table XIII and Fig. 7 give delivery within 1 s on the Chalakudy building topology with unlimited batteries. Without flooding OLSR delivers 100% in every window, DSDV 95.4-97.7% and AODV 86.2-91.2% (AODV below OLSR by a median of 9.0-9.7 points in the acute and sustained phases, Holm p = 0.0059). This gap grows with the time between bursts, to about 4, 9 and 12-15 points at mean gaps of 7.5, 15 and 30 s, and so do AODV's route discoveries per burst (1.6, 2.3 and 3.0), while AODV's PDR stays at 97-98%.")
table("chalakudy")
add("p", "With 25% of devices flooded, delivery within 1 s in the acute phase falls to 75.8% for OLSR, 72.3% for AODV and 70.2% for DSDV under the flood order, and to 75.9%, 75.9% and 65.8% under random failures; OLSR and AODV do not differ significantly here. Across the 12 flooded configurations without battery limits (both failure models, the share sweep and the traffic sweep), OLSR is significantly ahead of AODV in 4, at 10% flooded and with 30 s between bursts, and never behind (Table XIV, Fig. 10). At 50% flooded AODV and OLSR are level at about 57%. Counting only packets sent while a path existed, the protocols deliver 77-94% in the acute phase and 86-100% in the sustained phase (Fig. 8), so most of the loss after the onset falls on devices that were flooded or cut off. In the sustained phase all protocols deliver 51-60% within 1 s, with OLSR above AODV by a median of 5.5-6.9 points (Holm p = 0.0059), about the same gap as without flooding (Fig. 9).")
table("sweeps")
add("p", "<i>Flood order against random failures.</i> Failures ordered by real ground height and failures at random devices show no significant difference in delivery within 1 s in any of 87 comparisons (every protocol, window, onset, share, battery and traffic setting; smallest Holm p = 0.15). Counting only packets sent while a path existed, 2 of 78 comparisons reach p < 0.05, both in favour of the flood order in the acute phase (DSDV at 25% and OLSR at 50% flooded).")
add("p", "<i>Batteries.</i> With the assumed batteries and ns-3's radio currents, the last device runs flat 4, 7 and 14 hours of scenario time after the power cut when 25%, 50% and 100% of the battery is available to the radio, at the same time under every protocol, so nothing is sent in the sustained phase. Counted against every scheduled message, battery-limited runs deliver only 6-26%.")
add("p", "<i>Propagation.</i> Under the 3GPP path-loss model no packet was delivered in any of the 90 runs (184,731 sent): at a range of 62.8 m, 100 devices in the square do not form a network. All other results assume the 150 m unit disk.", sb_after=1)
fig("cwin")
fig("cconn")
fig("ctime")
fig("csens")

add("h1", "VI. Discussion", sb=2)
ph("Your text. Does the evidence support each half of the premise? Separate what the topology and traffic do (visible in the no-flood controls) from what flooding does. What can the battery results say about the sustained phase, given that every device ran flat within hours under every protocol? How much do the results depend on the 150 m range?")
add("h1", "VII. Limitations")
for lead, text in (
    ("Radio and network.", "Radio propagation is a 150 m unit disk; under a cited path-loss model the default radio reaches 62.8 m, and 100 devices in the Chalakudy square do not form a network. Devices are static, RTS/CTS is off, and all protocols use ns-3's default parameters."),
    ("Traffic.", "No data exist on message traffic during the floods, so all traffic is assumed: constant-rate flows in the main grid and bursts in the flood scenarios."),
    ("Energy.", "Only the Wi-Fi radio uses energy, with ns-3's default currents rather than those of a real 2018 device, and the battery size is a placeholder. With these values every device runs flat within hours of the power cut."),
    ("Time compression.", "One day lasts 30 simulated seconds for failures and batteries, but routing timers and traffic are not compressed."),
    ("Kerala-anchored model.", "Positions and terrain are synthetic, the flood curve and flooded shares are assumed, and the 27% figure comes from a press report."),
    ("Chalakudy data.", "Radar cannot see which buildings flooded and missed the flood peak; ground height comes from a surface model that includes roofs and trees; the square is nearly flat; the buildings are present-day map features, not the 2018 town; only one 1 km square is studied; and the flooded share, the number of devices per building and the power-cut date are assumed. The two onset dates come from press reports that disagree."),
    ("Statistics.", "With hundreds of tests, some p values below 0.05 are expected by chance."),
    ("Predictions.", "Predictions were not written down before the runs, so no result is a blind test of the premise."),
):
    add("p", f"<i>{lead}</i> {text}")
add("h1", "VIII. Conclusion")
ph("Your text: answer the research question in two or three sentences, then the main caveat and what you would do next.")
add("uh", "Acknowledgment")
add("p", "Building data © OpenStreetMap contributors and Overture Maps Foundation (ODbL). Municipality boundary: DataMeet (ODbL). Machine-detected building footprints: Google Open Buildings <hl>[VERIFY licence wording]</hl>. Contains modified Copernicus Sentinel data 2018. Copernicus DEM <hl>[VERIFY attribution wording on the Copernicus licence page]</hl>. <hl>[Thank anyone who helped.]</hl>")
add("uh", "Data Availability")
add("p", f'Code, inputs, raw simulation outputs and analysis are in the public repository [@repo]. Raw downloads (about 170 MB) are re-fetched by experiments/chalakudy_fetch.py, which records the URL, access time and SHA-256 of each file. The tables of this paper are in docs/paper/tables of the repository and in Google Sheets: <a href="{SHEET.format(SHEETS["main"])}">main grid</a>, <a href="{SHEET.format(SHEETS["sevload"])}">severity and load</a>, <a href="{SHEET.format(SHEETS["energy"])}">energy</a>, <a href="{SHEET.format(SHEETS["kerala"])}">Kerala-anchored scenario</a>, <a href="{SHEET.format(SHEETS["cwin"])}">Chalakudy windows</a> and <a href="{SHEET.format(SHEETS["csweep"])}">Chalakudy sweeps</a> (<a href="{FOLDER}">folder</a>); docs/paper/tests.csv lists every paired test. <hl>[Before submission: add an ODbL notice for the derived data and a licence for the code; the repository has none.]</hl>')
add("uh", "References")
add("refs")
add("uh", "Appendix A: Chalakudy Parameters", sb=1)
add("p", "Table XV condenses data/chalakudy/PROVENANCE.md, which gives all 43 parameters with their sources and reasoning.")
table("params", wide=True)
add("uh", "Appendix B: Sentinel-1 Scenes")
add("p", "Reference water detected is the share of cells inside mapped rivers and ponds that are classified as water; far land as water is the share of land at least 150 m from mapped water that is classified as water, which bounds false detections in dry scenes (on 16 Jul, 9 Aug and 21 Aug part of it may be real flooding). Fig. 11 checks where the radar maps are placed.")
table("scenes", wide=True)
fig("qa")
add("uh", "Appendix C: Timeline")
table("timeline", wide=True)

# ---------------------------------------------------------------- citations -> numbers
order = []


def cite(m_):
    keys = [k.strip().lstrip("@") for k in m_.group(1).split(",")]
    for k in keys:
        if k not in REFS:
            sys.exit(f"unknown reference {k}")
        if k not in order:
            order.append(k)
    return ", ".join(f"[{order.index(k) + 1}]" for k in keys)


CITE = re.compile(r"\[(@[\w-]+(?:,\s*@[\w-]+)*)\]")
KEEP = re.compile(r"(https?://\S+|2026-10-21\.0|10\.5270/ESA-c5d3d65|6\.2\.1-1)")


def typo(s):
    """En dash in numeric ranges, minus sign before negative numbers; URLs and identifiers unchanged."""
    parts = KEEP.split(s)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"(?<=\d)-(?=\d)", "\u2013", parts[i])
        parts[i] = re.sub(r"(^|[\s(])-(?=\d)", "\\1\u2212", parts[i])
    return "".join(parts)

expanded = []
for b in B:
    if b["kind"] == "refs":
        continue
    b["text"] = typo(CITE.sub(cite, b["text"]))
    if b["kind"] == "tcap":
        rows = T[b["table"]][1]
        T[b["table"]] = (T[b["table"]][0], [[typo(CITE.sub(cite, str(x))) for x in row] for row in rows], T[b["table"]][2])
missing = [k for k in REFS if k not in order]
if missing:
    sys.exit(f"references never cited: {missing}")
for b in B:
    if b["kind"] == "refs":
        i = B.index(b)
        B[i:i + 1] = [dict(kind="ref", text=typo(f"[{n + 1}] {REFS[k]}")) for n, k in enumerate(order)]
        break

# ---------------------------------------------------------------- inline markup
TAG = re.compile(r'<(/?)(b|i|hl|a)(?: href="([^"]*)")?>')


def parse(s):
    out, spans, stack, pos = [], [], [], 0
    for mt in TAG.finditer(s):
        out.append(s[pos:mt.start()])
        pos = mt.end()
        here = sum(len(x) for x in out)
        if mt.group(1):
            tag, start, href = stack.pop()
            if tag != mt.group(2):
                sys.exit(f"bad nesting in {s[:60]}")
            spans.append((start, here, tag, href))
        else:
            stack.append((mt.group(2), here, mt.group(3)))
    out.append(s[pos:])
    if stack:
        sys.exit(f"unclosed tag in {s[:60]}")
    return "".join(out), spans


def u16(s):
    return len(s.encode("utf-16-le")) // 2


# ---------------------------------------------------------------- styles per block kind
JUST, CENTER, START = "JUSTIFIED", "CENTER", "START"
PARA = {   # kind -> (named style, alignment, spaceAbove, spaceBelow, indentFirstLine, indentStart, indentEnd, keepWithNext)
    "title": ("TITLE", CENTER, 0, 8, 0, 0, 0, True),
    "authors": ("NORMAL_TEXT", CENTER, 0, 2, 0, 0, 0, True),
    "affil": ("NORMAL_TEXT", CENTER, 0, 14, 0, 0, 0, False),
    "abstract": ("NORMAL_TEXT", JUST, 0, 4, 10, 0, 0, False),
    "index": ("NORMAL_TEXT", JUST, 0, 6, 10, 0, 0, False),
    "h1": ("HEADING_1", CENTER, 10, 4, 0, 0, 0, True),
    "uh": ("HEADING_1", CENTER, 10, 4, 0, 0, 0, True),
    "h2": ("HEADING_2", START, 6, 2, 0, 0, 0, True),
    "p": ("NORMAL_TEXT", JUST, 0, 0, 10, 0, 0, False),
    "quote": ("NORMAL_TEXT", JUST, 3, 3, 14, 14, 14, False),
    "tcap": ("NORMAL_TEXT", CENTER, 8, 3, 0, 0, 0, True),
    "fig": ("NORMAL_TEXT", CENTER, 8, 2, 0, 0, 0, True),
    "fcap": ("NORMAL_TEXT", JUST, 0, 8, 0, 0, 0, False),
    "ref": ("NORMAL_TEXT", JUST, 0, 2, 0, 16, 0, False),
}
TEXT = {   # kind -> extra text style over the 10 pt Times base
    "title": {"fontSize": pt(24), "bold": False},
    "authors": {"fontSize": pt(11)},
    "affil": {"fontSize": pt(9), "italic": True},
    "abstract": {"fontSize": pt(9), "bold": True},
    "index": {"fontSize": pt(9), "bold": True},
    "h1": {"fontSize": pt(10), "bold": False, "italic": False, "smallCaps": True},
    "uh": {"fontSize": pt(10), "bold": False, "italic": False, "smallCaps": True},
    "h2": {"fontSize": pt(10), "bold": False, "italic": True},
    "quote": {"italic": True},
    "tcap": {"fontSize": pt(8)},
    "fig": {"fontSize": pt(8)},
    "fcap": {"fontSize": pt(8)},
    "ref": {"fontSize": pt(8)},
}
YELLOW = {"color": {"rgbColor": {"red": 1, "green": 0.949, "blue": 0.8}}}


def layout():
    """Plain text of the body and each block's [start, end) in the document after the insert."""
    pos, texts = 1, []
    for b in B:
        plain, spans = parse(b["text"])
        b["plain"], b["spans"] = plain, spans
        b["start"] = pos
        b["end"] = pos + u16(plain) + 1
        pos = b["end"]
        texts.append(plain)
    return "\n".join(texts), pos


def merged(key):
    """Consecutive blocks with the same style value, as (start, end, value)."""
    out = []
    for b in B:
        v = key(b)
        if v is None:
            continue
        if out and out[-1][2] == v and out[-1][1] == b["start"]:
            out[-1][1] = b["end"]
        else:
            out.append([b["start"], b["end"], v])
    for o in out:          # stop before the body's final newline
        o[1] = min(o[1], B[-1]["end"] - 1)
    return [o for o in out if o[1] > o[0]]


def rng(a, z):
    return {"startIndex": a, "endIndex": z}


PFIELDS = ("namedStyleType", "alignment", "spaceAbove", "spaceBelow", "indentFirstLine", "indentStart", "indentEnd",
           "keepWithNext")


def para_style(kind):
    v = PARA[kind]
    return {f: (pt(x) if f.startswith(("space", "indent")) else x) for f, x in zip(PFIELDS, v)}


def batch_text(rev, part):
    """Batch A in three parts: 1 = replace the text and set the body style; 2 = paragraph styles of
    everything that is not body text; 3 = text styles, inline markup and the section breaks."""
    text, end = layout()
    req = []
    if part == 1:
        base = dict(para_style("p"), lineSpacing=100, keepLinesTogether=False)
        req = [{"deleteContentRange": {"range": rng(1, OLD_END - 1)}},
               {"insertText": {"location": {"index": 1}, "text": text}},
               {"updateDocumentStyle": {"documentStyle": {"marginTop": pt(54), "marginBottom": pt(64),
                                                           "marginLeft": pt(45), "marginRight": pt(45)},
                                        "fields": "marginTop,marginBottom,marginLeft,marginRight"}},
               {"updateTextStyle": {"range": rng(1, end - 1), "textStyle": {"weightedFontFamily": FONT,
                                                                            "fontSize": pt(10)}, "fields": "*"}},
               {"updateParagraphStyle": {"range": rng(1, end - 1), "paragraphStyle": base, "fields": ",".join(base)}}]
    elif part == 2:
        body = para_style("p")
        for a, z, v in merged(lambda b: None if b["kind"] == "p" else b["kind"]):
            st = {f: x for f, x in para_style(v).items() if x != body[f] or f == "namedStyleType"}
            req.append({"updateParagraphStyle": {"range": rng(a, z), "paragraphStyle": st, "fields": ",".join(st)}})
    else:
        for a, z, v in merged(lambda b: json.dumps(TEXT[b["kind"]]) if b["kind"] in TEXT else None):
            style = json.loads(v)
            req.append({"updateTextStyle": {"range": rng(a, z), "textStyle": style, "fields": ",".join(style)}})
        for b in B:
            base = b["start"]
            for s, z, tag, href in b["spans"]:
                if z <= s:
                    continue
                r_ = rng(base + u16(b["plain"][:s]), base + u16(b["plain"][:z]))
                if tag == "b":
                    st, f = {"bold": True}, "bold"
                elif tag == "i":
                    st, f = {"italic": True}, "italic"
                elif tag == "hl":
                    st, f = {"backgroundColor": YELLOW}, "backgroundColor"
                else:
                    st, f = {"link": {"url": href}}, "link"
                req.append({"updateTextStyle": {"range": r_, "textStyle": st, "fields": f}})
            if b["kind"] in ("abstract", "index"):      # "Abstract—": bold italic label
                dash = b["plain"].index("—") + 1
                req.append({"updateTextStyle": {"range": rng(base, base + dash),
                                                "textStyle": {"bold": True, "italic": True}, "fields": "bold,italic"}})
        # section breaks, bottom-up: a break before a block with sb=N starts an N-column section
        for b in B:
            if b.get("sb_after"):
                B[B.index(b) + 1]["sb"] = 1
        breaks = sorted((b for b in B if b.get("sb")), key=lambda b: b["start"])
        for b in reversed(breaks):
            req.append({"insertSectionBreak": {"location": {"index": b["start"]}, "sectionType": "CONTINUOUS"}})
        for k, b in enumerate(breaks):
            p = b["start"] + 2 * k          # the empty paragraph Google adds before the break
            req.append({"updateParagraphStyle": {"range": rng(p, p + 1), "paragraphStyle": {
                "namedStyleType": "NORMAL_TEXT", "spaceAbove": pt(0), "spaceBelow": pt(0), "keepWithNext": False,
                "indentFirstLine": pt(0), "alignment": START},
                "fields": "namedStyleType,spaceAbove,spaceBelow,keepWithNext,indentFirstLine,alignment"}})
            req.append({"updateTextStyle": {"range": rng(p, p + 1), "textStyle": {"fontSize": pt(1)},
                                            "fields": "fontSize"}})
            if b["sb"] == 2:
                x = b["start"] + 2 * k + 2
                req.append({"updateSectionStyle": {"range": rng(x, x + 1), "sectionStyle": {
                    "columnProperties": [{"paddingEnd": pt(COL_GAP)}, {"paddingEnd": pt(0)}]},
                    "fields": "columnProperties"}})
    return {"requests": req, "writeControl": {"requiredRevisionId": rev}}


def shifted(i):
    """Index after the section breaks of part 3: each break adds 2 indexes at the block it precedes."""
    return i + 2 * sum(1 for b in B if b.get("sb") and b["start"] <= i)


def batch_fix(rev, doc_end):
    """Times New Roman over the whole body and 10 pt on body paragraphs (setting a paragraph's
    named style in parts 1-2 cleared the body text's font)."""
    layout()
    for b in B:
        if b.get("sb_after"):
            B[B.index(b) + 1]["sb"] = 1
    req = [{"updateTextStyle": {"range": rng(1, doc_end - 1), "textStyle": {"weightedFontFamily": FONT},
                                "fields": "weightedFontFamily"}}]
    for a, z, v in merged(lambda b: "body" if b["kind"] in ("p", "quote") else None):
        req.append({"updateTextStyle": {"range": rng(shifted(a), shifted(z - 1) + 1), "textStyle": {"fontSize": pt(10)},
                                        "fields": "fontSize"}})
    return {"requests": req, "writeControl": {"requiredRevisionId": rev}}


# ---------------------------------------------------------------- batch B: tables and figures
def doc_paragraphs(doc):
    """(start, end, text) of every body paragraph outside tables."""
    while isinstance(doc, dict) and "content" in doc and not isinstance(doc.get("content"), list):
        doc = doc["content"]
        if isinstance(doc, str):
            doc = json.loads(doc)
    body = doc["tabs"][0]["documentTab"]["body"]["content"] if "tabs" in doc else doc["body"]["content"]
    out = []
    for el in body:
        if "paragraph" in el:
            t = "".join(e.get("textRun", {}).get("content", "") for e in el["paragraph"]["elements"])
            out.append((el["startIndex"], el["endIndex"], t))
    return doc.get("revisionId"), out


GREY = {"color": {"rgbColor": {"red": 0.85, "green": 0.85, "blue": 0.85}}}
BORDER = {"color": {"color": {"rgbColor": {"red": 0.35, "green": 0.35, "blue": 0.35}}}, "width": pt(0.5), "dashStyle": "SOLID"}
TEXT_HEAVY = {"timers", "config", "experiments", "scenarios", "data", "params", "timeline"}


def table_requests(key, at):
    _, rows, widths = T[key]
    R, C = len(rows), max(len(r) for r in rows)
    S, stride = at + 1, 2 * C + 1
    req = [{"insertTable": {"rows": R, "columns": C, "location": {"index": at}}}]
    after = S + 2 + R * stride
    req.append({"updateParagraphStyle": {"range": rng(after, after + 1), "paragraphStyle": {
        "namedStyleType": "NORMAL_TEXT", "spaceAbove": pt(0), "spaceBelow": pt(6), "keepWithNext": False,
        "alignment": START, "indentFirstLine": pt(0)},
        "fields": "namedStyleType,spaceAbove,spaceBelow,keepWithNext,alignment,indentFirstLine"}})
    req.append({"updateTextStyle": {"range": rng(after, after + 1), "textStyle": {"fontSize": pt(4), "weightedFontFamily": FONT},
                                    "fields": "fontSize,weightedFontFamily"}})
    cells = [(r, c, str(rows[r][c]) if c < len(rows[r]) else "") for r in range(R) for c in range(C)]
    for r, c, t in reversed(cells):
        if t:
            req.append({"insertText": {"location": {"index": S + 3 + r * stride + 2 * c}, "text": t}})
    total = sum(u16(t) for _, _, t in cells)
    end = S + 2 + R * stride + total            # first index after the table
    req.append({"updateParagraphStyle": {"range": rng(S, end), "paragraphStyle": {
        "alignment": START if key in TEXT_HEAVY else CENTER, "spaceAbove": pt(0), "spaceBelow": pt(0),
        "keepWithNext": False, "indentFirstLine": pt(0), "indentStart": pt(0), "lineSpacing": 100},
        "fields": "alignment,spaceAbove,spaceBelow,keepWithNext,indentFirstLine,indentStart,lineSpacing"}})
    req.append({"updateTextStyle": {"range": rng(S, end), "textStyle": {"weightedFontFamily": FONT, "fontSize": pt(8),
                                                                        "bold": False, "italic": False},
                                    "fields": "weightedFontFamily,fontSize,bold,italic"}})
    shift = 0
    for c in range(C):
        t = cells[c][2]
        a = S + 3 + 2 * c + shift
        if t:
            req.append({"updateTextStyle": {"range": rng(a, a + u16(t)), "textStyle": {"bold": True}, "fields": "bold"}})
        shift += u16(t)
    loc = {"index": S}
    req.append({"updateTableCellStyle": {"tableStartLocation": loc, "tableCellStyle": {
        "paddingLeft": pt(3), "paddingRight": pt(3), "paddingTop": pt(1), "paddingBottom": pt(1),
        "borderLeft": BORDER, "borderRight": BORDER, "borderTop": BORDER, "borderBottom": BORDER},
        "fields": "paddingLeft,paddingRight,paddingTop,paddingBottom,borderLeft,borderRight,borderTop,borderBottom"}})
    req.append({"updateTableCellStyle": {"tableRange": {"tableCellLocation": {"tableStartLocation": loc, "rowIndex": 0,
                                                                              "columnIndex": 0},
                                                        "rowSpan": 1, "columnSpan": C},
                                         "tableCellStyle": {"backgroundColor": GREY}, "fields": "backgroundColor"}})
    for c, w in enumerate(widths):
        req.append({"updateTableColumnProperties": {"tableStartLocation": loc, "columnIndices": [c],
                                                    "tableColumnProperties": {"widthType": "FIXED_WIDTH", "width": pt(w)},
                                                    "fields": "widthType,width"}})
    return req


def figure_requests(key, s, e):
    path, width, w, h, _ = FIGS[key]
    return [{"deleteContentRange": {"range": rng(s, e - 1)}},
            {"insertInlineImage": {"uri": RAW + path, "location": {"index": s},
                                   "objectSize": {"width": pt(width), "height": pt(round(width * h / w, 1))}}}]


def batch_objects(read_path, rev, chunk, nchunks=int(os.environ.get("NCHUNKS", 6))):
    _, paras = doc_paragraphs(json.load(open(read_path)))
    items = []
    for s, e, t in paras:
        mt = re.match(r"\{\{F:(\w+)\}\}\n", t)
        if mt:
            items.append((s, "fig", mt.group(1), e))
        mt = re.match(r"TABLE ([IVX]+): ", t)
        if mt:
            key = [k for k, n in TN.items() if roman(n) == mt.group(1)][0]
            items.append((s, "table", key, e))
    if len(items) != len(TN) + len(FN):
        sys.exit(f"found {len(items)} objects, expected {len(TN) + len(FN)}")
    items.sort(reverse=True)         # bottom-up: each insert leaves the positions above it unchanged
    weights = [len(T[k][1]) * len(T[k][1][0]) if kind == "table" else 3 for _, kind, k, _ in items]
    total, acc, groups = sum(weights), 0, [[] for _ in range(nchunks)]
    for it, w in zip(items, weights):
        groups[min(nchunks - 1, int(acc * nchunks / total))].append(it)
        acc += w
    req = []
    for s, kind, key, e in groups[chunk]:
        req += table_requests(key, e - 1) if kind == "table" else figure_requests(key, s, e)
    return {"requests": req, "writeControl": {"requiredRevisionId": rev}}, [k for _, _, k, _ in groups[chunk]]


# ---------------------------------------------------------------- Markdown copy for the repository
def markdown():
    layout()
    md = []
    for b in B:
        t = b["plain"]
        k = b["kind"]
        if k == "title":
            md.append(f"# {t}\n")
        elif k in ("h1", "uh"):
            md.append(f"\n## {t}\n")
        elif k == "h2":
            md.append(f"\n### {t}\n")
        elif k == "quote":
            md.append(f"> {t}\n")
        elif k == "abstract" or k == "index":
            md.append(f"**{t}**\n")
        elif k == "fig":
            key = b["figure"]
            md.append(f"![]({os.path.relpath(os.path.join(REPO, FIGS[key][0]), os.path.join(REPO, 'docs', 'paper'))})\n")
        elif k == "fcap":
            md.append(f"*{t}*\n")
        elif k == "tcap":
            rows = T[b["table"]][1]
            md.append(f"**{t}**\n")
            md.append("| " + " | ".join(rows[0]) + " |")
            md.append("|" + "---|" * len(rows[0]))
            for row in rows[1:]:
                md.append("| " + " | ".join(str(x) for x in row) + " |")
            md.append("")
        else:
            md.append(f"{t}\n")
    path = os.path.join(REPO, "docs", "paper", "paper.md")
    open(path, "w").write("\n".join(md) + "\n")
    print("wrote", path)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "text":
        out = batch_text(sys.argv[2], int(sys.argv[3]))
        p = os.path.join(OUT, f"batchA{sys.argv[3]}.json")
        json.dump(out, open(p, "w"), ensure_ascii=False, separators=(",", ":"))
        print(p, os.path.getsize(p), "bytes,", len(out["requests"]), "requests")
    elif cmd == "objects":
        out, keys = batch_objects(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        p = os.path.join(OUT, f"batchB{sys.argv[4]}.json")
        json.dump(out, open(p, "w"), ensure_ascii=False, separators=(",", ":"))
        print(p, os.path.getsize(p), "bytes,", len(out["requests"]), "requests:", keys)
    elif cmd == "fix":
        out = batch_fix(sys.argv[2], int(sys.argv[3]))
        p = os.path.join(OUT, "batchFix.json")
        json.dump(out, open(p, "w"), ensure_ascii=False, separators=(",", ":"))
        print(p, os.path.getsize(p), "bytes,", len(out["requests"]), "requests")
    elif cmd == "markdown":
        markdown()
