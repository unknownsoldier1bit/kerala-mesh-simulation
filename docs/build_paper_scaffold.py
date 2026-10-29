"""Builds docs/paper-scaffold.html: the paper's structure, notes on what goes where, and the factual tables."""
import json, html
REPO = "/home/user/kerala-mesh-simulation"
ds = json.load(open(f"{REPO}/data/chalakudy/data_summary.json"))

def note(t):
    return f'<p><i><span style="color:#808080">[Note: {t}]</span></i></p>\n'

def yours(t="Your text here."):
    return f'<p><span style="background-color:#fff2cc">{t}</span></p>\n'

def table(head, rows):
    s = '<table border="1" cellpadding="4" style="border-collapse:collapse">\n<tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr>\n"
    for r in rows:
        s += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n"
    return s + "</table>\n"

def bullets(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>\n"

P = []
a = P.append
a('<html><head><meta charset="utf-8"><title>Paper draft</title></head><body>')
a('<h1>[Title: yours to write]</h1>')
a('<p>[Authors]</p>')
a(note("This scaffold was generated from the repository (branch chalakudy-buildings) on 29 Oct 2026. Grey italic notes are instructions: delete them as you write. Yellow boxes are where your prose goes. Tables and numbers come from the repo (docs/paper-data-guide.md, data/chalakudy/data_summary.json, experiments/README.md); if a table and the repo ever disagree, the repo wins. VERIFY = check before citing; NEEDS URL = record the URL before citing. Per CLAUDE.md you write the reasoning (premise, mechanism, discussion); Claude critiques."))

a('<h2>Abstract</h2>')
a(note("Write this last, 150-250 words. Include: the question; what was simulated (AODV, OLSR and DSDV in ns-3.47; a time-evolving failure model anchored to the Kerala 2018 floods; a scenario on real building positions in Chalakudy); the primary metric (share of messages delivered within a deadline T); the main finding; the main caveat (results assume a 150 m radio range; batteries and traffic are assumed)."))
a(yours())

a('<h2>1. Introduction</h2>')
a(note("Context to draw on, with sources: in August 2018 communications failed across flood-hit Kerala; the CAG (Report No. 6 of 2021, section 3.5.2) records a total communications failure in Chalakudy and Idukki taluks; a press report of the Telecom Secretary's review gives about 27% of base stations down statewide (press only: say so). If you give a death toll, name its source (sources give 339, 433, 474 or 483)."))
a(note("Say 'mesh nodes' or 'mobile devices', never 'phones'. State the gap: plain AODV-vs-OLSR comparisons are common; this paper's contribution is the time-evolving, Kerala-anchored failure model, including a scenario built on real building positions and 2018 data."))
a('<p><b>Premise (your words, from CLAUDE.md; keep or quote as written):</b></p>')
a('<blockquote>During the acute phase of a flood such as Kerala 2018, OLSR delivers a higher fraction of messages within a fixed deadline than AODV. OLSR keeps routes computed in advance, so a message can leave immediately. AODV has to discover a route first, and again after every link break. With frequent breaks and short bursts of traffic, that discovery delay uses up much of the deadline. The advantage has a cost: OLSR\'s periodic control traffic drains batteries faster. So over the sustained phase, as nodes run out of power, AODV should close the gap or overtake it.</blockquote>')
a(note("Then your research question(s) and a short list of contributions. Decide whether DSDV stays in the paper: it was included because the deliverables list asked for it."))
a(yours())

a('<h2>2. Background</h2>')
a('<h3>2.1 AODV</h3>' + note("Reactive: routes are found on demand (RREQ flood, RREP back) and expire when unused. Cite RFC 3561 (VERIFY)."))
a(yours())
a('<h3>2.2 OLSR</h3>' + note("Proactive: periodic HELLO and TC messages keep a full routing table; multipoint relays limit flooding. Cite RFC 3626 (VERIFY)."))
a(yours())
a('<h3>2.3 DSDV (if kept)</h3>' + note("Proactive distance-vector with sequence numbers. Cite Perkins and Bhagwat, SIGCOMM 1994 (VERIFY)."))
a(yours())
a('<p><b>Table 1. ns-3.47 default timers used in every run</b> (checked in the ns-3 source; docs/ns3-defaults.md)</p>')
a(table(["Protocol", "Setting", "Value"], [
    ["OLSR", "HELLO interval / neighbour hold time", "2 s / 6 s"],
    ["OLSR", "TC interval", "5 s"],
    ["AODV", "HELLO interval / allowed HELLO loss", "1 s / 2"],
    ["AODV", "Active route timeout", "3 s"],
    ["AODV", "RREQ retries", "2"],
    ["DSDV", "Periodic update interval / settling time", "15 s / 5 s"],
    ["DSDV", "Route dropped after", "45 s without an update"],
    ["Link-break detection", "AODV: MAC retry-limit feedback and missing HELLOs; OLSR: no HELLO for 6 s; DSDV: no update for 45 s", ""],
]))
a('<h3>2.4 Related work</h3>')
a(note("No related-work papers were read or verified in this project. Find and read them yourself; cite only what you have opened."))
a(yours())

a('<h2>3. Mechanism</h2>')
a(note("Your mechanism paragraph (CLAUDE.md, step 2: you write this). Why should OLSR deliver more messages within T in the acute phase, and why should AODV close the gap in the sustained phase? Keep it to the mechanism; the results come later."))
a(yours())

a('<h2>4. Methods</h2>')
a('<h3>4.1 Simulator and network</h3>')
a(note("Describe the setup in prose and keep the table. Full details: experiments/README.md section 1; every run's exact settings are in its run_config.json."))
a(yours())
a('<p><b>Table 2. Simulation configuration</b></p>')
a(table(["Item", "Setting"], [
    ["Simulator", "ns-3.47, optimized build"],
    ["Protocols", "AODV, OLSR, DSDV with ns-3 default parameters"],
    ["Radio and MAC", "IEEE 802.11b ad hoc; data at 11 Mbps, control frames and broadcasts at 1 Mbps; 16.02 dBm transmit power (ns-3 default); RTS/CTS off; ARP tables pre-filled"],
    ["Radio range", "150 m unit disk: full signal within 150 m, nothing beyond (assumed; a cited path-loss model is a sensitivity run)"],
    ["Topologies", "Main grid: 25, 50 or 100 nodes placed at random in a 500 m square, redrawn until connected. Chalakudy: 100 devices at real building positions in a 1 km square"],
    ["Mobility", "None (static nodes)"],
    ["Traffic", "UDP, 512-byte payload. Main grid: 10 constant-rate flows, 4 packets/s, 60-290 s. Kerala and Chalakudy: 20 flows of bursts (5 packets 0.2 s apart, exponential gaps averaging 15 s), 60-448 s"],
    ["Duration", "300 s (main grid, severity, load); 600 s (energy); 450 s (Kerala, Chalakudy)"],
    ["Warm-up", "60 s without traffic"],
    ["Repetitions", "Seeds 1-10 per configuration; paired: for a seed every protocol sees the same topology, traffic and failures"],
]))
a('<h3>4.2 Metrics</h3>')
a(note("Primary metric: share of sent messages delivered within a deadline T. T = 1 s is a placeholder until set from Kerala data; 0.5, 2 and 5 s are also in the tables. Also report: PDR; connected PDR (only packets sent while a path existed: the connectivity control); delivery of scheduled messages (counts messages a dead source could not send; use it for battery-limited runs); delay; control overhead; recovery time; energy. Definitions: experiments/README.md section 3."))
a(yours())
a('<h3>4.3 Experiments</h3>')
a(note("Choose which experiments the paper reports. All 2,316 runs (13 experiments) finished without failures."))
a(table(["Experiment", "What varies", "Runs"], [
    ["main", "3 protocols x 6 scenarios x 25/50/100 nodes x seeds 1-10", "540"],
    ["severity", "random relay nodes or links, 5/10/20/30%, 50 nodes", "240"],
    ["load", "baseline or node failure, 5/10/20 flows, 50 nodes", "180"],
    ["energy", "2 radio profiles, batteries run out, 50 nodes", "60"],
    ["kerala / kerala100", "no-flood control, Kerala-anchored 27% and 50%, random 27% and 50%; 50 or 100 nodes", "150 + 150"],
    ["rtscts100", "100-node baseline with RTS/CTS on (sensitivity)", "30"],
    ["chalakudy", "control, flood 25% (lowest ground first), uniform random 25%; onset 15 or 17 Aug; batteries unlimited or limited; 100 devices", "360"],
    ["chalakudy_prop", "cited log-distance path-loss model instead of the 150 m disk", "90"],
    ["chalakudy_share", "10% and 50% flooded", "120"],
    ["chalakudy_battery", "25% and 100% of the battery for the radio", "180"],
    ["chalakudy_traffic", "mean gap between bursts 7.5 s and 30 s", "180"],
    ["chalakudy_check", "cross-checks (FlowMonitor, ns-3 energy framework), 50 devices, seeds 1-2", "36"],
]))
a('<h3>4.4 Abstract failure scenarios (main grid)</h3>')
a(table(["Scenario", "What fails", "When", "Selection"], [
    ["baseline", "nothing", "-", "-"],
    ["link_fail", "the 5 links carrying the most traffic", "120 s, permanent", "deterministic"],
    ["node_fail", "the busiest 10% of relays", "120 s, permanent", "deterministic"],
    ["multi_fail", "three waves of 5% of relays and 5% of links", "120, 135, 150 s", "random (seeded)"],
    ["partition", "every link crossing the vertical midline", "120-210 s, then restored", "deterministic"],
    ["recovery", "the same relays as node_fail", "120-210 s, then restored", "deterministic"],
]))
a('<h3>4.5 Kerala-anchored failure model</h3>')
a(note("Synthetic positions and terrain, real dates. Facts: 1 day = 30 simulated seconds (factor 2,880), 14 Aug 00:00 at 60 s, end on 27 Aug (last Thrissur substation back on, KSEB: NEEDS URL). Acute phase 14-18 Aug: nodes fail as water rises, following an assumed curve (0, 15, 60, 90 and 100% of eventual flood failures by 14, 15, 16, 17 and 18 Aug). 27% (press-reported statewide tower outage, used as a floor) or 50% (hypothetical) of nodes flood. Synthetic terrain: river on the west edge, ground rising eastward plus noise; lowest nodes fail first. Uniform-random baseline with the same counts and times; no-flood control. Sustained phase 18-27 Aug: no recharging; each battery would last, idling only, until a random date between 19 Aug and 6 Sep. Say plainly that this is a hypothetical scenario anchored to dated events, not measured Kerala data."))
a(yours())

a('<h3>4.6 Chalakudy scenario: data</h3>')
a(note("Data sources, processing and numbers: docs/paper-data-guide.md sections 2-4. Every input is labelled MEASURED, DERIVED or ASSUMED in data/chalakudy/PROVENANCE.md; say so in one sentence and put the condensed table in the appendix (Appendix A). Figure 1: results/analysis_chalakudy/figures/chalakudy_study_area. Caption credit: '(c) OpenStreetMap contributors, Overture Maps Foundation; contains modified Copernicus Sentinel data 2018'."))
m, sq = ds["municipality"], ds["study_square"]
s1 = ds["sentinel1"]
a('<p><b>Table 3. Data for the Chalakudy scenario</b></p>')
a(table(["Item", "Source", "Value used", "Kind"], [
    ["Municipality boundary", "DataMeet Indian Village Boundaries (ODbL)", f"Chalakudy (Thrissur district), {m['area_km2']} km2", "Measured"],
    ["Buildings", "Overture Maps 2026-10-21.0 (Google Open Buildings, OpenStreetMap)", f"{m['buildings']:,} in the municipality ({m['buildings_by_source']['Google Open Buildings']:,} Google, {m['buildings_by_source']['OpenStreetMap']:,} OSM); median footprint {m['footprint_m2']['p50']:.0f} m2", "Measured"],
    ["Study square", "rule applied to the data", f"1 km x 1 km, the most buildings among the town's lowest 25%; {sq['buildings']:,} buildings", "Derived (rule assumed)"],
    ["Ground height", "Copernicus DEM GLO-30 (surface model)", f"5th percentile within 50 m of each building; square median {sq['ground_estimate_m']['p50']:.1f} m (10th-90th percentile {sq['ground_estimate_m']['p10']:.1f}-{sq['ground_estimate_m']['p90']:.1f} m)", "Derived"],
    ["Water on 24 dates", "Sentinel-1 IW GRDH, Jan-Sep 2018", f"{s1['scenes']} scenes; no image between 9 and 21 Aug; thresholds {s1['threshold_db_range'][0]:.1f} to {s1['threshold_db_range'][1]:.1f} dB", "Measured / derived"],
    ["Flood water in the municipality", "derived from the radar maps", "0.98 km2 on 9 Aug and 21 Aug; 0.25 km2 on 27 Aug", "Derived"],
    ["Nearest radar-visible flood water to any building in the square", "derived", f"{ds['study_square']['distance_to_radar_flood_water']['2018-08-21_des']['nearest_m']:.0f} m (21 Aug, descending); none within 50 m on any date", "Derived"],
    ["Devices", "random buildings, seeds 1-10", "100 per run (100 per km2); mean degree 7.2; largest connected group 97%", "Assumed (positions measured)"],
]))
a(yours())

a('<h3>4.7 Chalakudy scenario: failures, batteries, traffic, time</h3>')
a(note("Three comparisons per seed, same devices and flows: (1) flood order: 25% of devices fail (10% and 50% swept), evenly spaced from the onset day (15 or 17 Aug; the sources disagree, both are run) to 18 Aug 00:00, lowest ground first (in this square no building is near radar-visible flood water, so ground height alone sets the order); flooded devices do not return. (2) Uniform random: same counts and times at random devices. (3) No-flood control. The flood pattern is only moderately clustered: nearest other failed device 83 m (flood) vs 104 m (random). Batteries (battery-limited runs only, all assumed): random charge 20-100% x share for the radio (50%; 25% and 100% swept) x 3,000 mAh x 3.85 V placeholder, scaled by the time compression; radio off at 10%; ns-3 default radio currents (0.82 W idle, Wi-Fi radio only). Power cut assumed at 00:00 on the onset day; run ends 27 Aug. Time: 1 day = 30 s; routing timers and traffic are not compressed (a 15 s gap between bursts spans 12 scenario hours)."))
a(yours())

a('<h3>4.8 Propagation sensitivity</h3>')
a(note("Replaces the 150 m disk with the 3GPP TR 37.885 V2V-Urban NLOS path-loss formula, PL = 36.85 + 30 log10(d) + 18.9 log10(f), f = 2.412 GHz, as implemented in ns-3.47, nothing adjusted. With ns-3 default transmit power and preamble-detection threshold (-82 dBm) frames get through up to 62.8 m (checked with two devices: 100% at 62.5 m, 0% at 63 m). NLOS for every link is assumed; the model was made for vehicles, not devices in houses."))
a(yours())

a('<h3>4.9 Statistics</h3>')
a(note("Means with 95% confidence intervals (t-distribution) over 10 seeds. Paired tests across seeds: Friedman over the three protocols, then two-sided Wilcoxon signed-rank tests per pair with Holm correction over the three pairs (flood vs uniform: Wilcoxon per protocol, Holm over protocols). With 10 paired seeds the smallest possible Holm-corrected p is 0.0059. Holm covers only the pairs within one configuration and metric: across hundreds of tests some p < 0.05 are expected by chance, so weigh differences that hold across configurations. Cite Friedman 1937, Wilcoxon 1945, Holm 1979 (VERIFY)."))
a(yours())

a('<h3>4.10 Validation</h3>')
a(note("Checks to report: the diamond sanity simulation; the packet tracker agrees with ns-3 FlowMonitor (exactly in the Chalakudy cross-check runs); the state-based energy count agrees with ns-3's energy framework when batteries are effectively unlimited; every run's metrics recompute identically from its raw files and the analysis reproduces byte for byte; on a second machine 467 of 482 replayed runs matched exactly (the other 15, dense 100-node AODV runs, differ run by run but agree on average). Problems found and fixed: OLSR packets fragmented at 100+ nodes crashed or (in 29 earlier runs) slightly undercounted the control-traffic counter, fixed and redone; ns-3's energy framework does not drain a finite battery correctly, so batteries use the state-based model. Details: experiments/README.md section 6, docs/ns3-defaults.md."))
a(yours())

a('<h2>5. Results</h2>')
a(note("Report means with 95% CIs and Holm-corrected p values; numbers are in results/analysis/FINDINGS.md and results/analysis_chalakudy/FINDINGS.md. Compare every flood result with the no-flood control of the same nodes: a difference already present in the control is not a flood effect. Error bars on percentages are clipped to 0-100%. Every Chalakudy caption must say what is real data and what is assumed (the generated figures already do)."))
a('<h3>5.1 Main grid (density and failure scenarios)</h3>' + note("Figures: main_within_1s, main_pdr, density_within_1s, main_delay_mean, main_control_per_node_s, main_recovery_after_failure (results/analysis/figures)."))
a(yours())
a('<h3>5.2 Failure severity and traffic load</h3>' + note("Figures: severity_within_1s, severity_pdr, load_pdr, load_delay_mean."))
a(yours())
a('<h3>5.3 Energy</h3>' + note("Figures: energy_lifetime, energy_over_time, main_energy_per_node. In ns-3's radio model idle listening dominates energy use."))
a(yours())
a('<h3>5.4 Kerala-anchored scenario</h3>' + note("Figures: kerala_within_T_by_phase_n50 and n100, kerala_over_time_n50 and n100, kerala_deadline_sweep_n50 and n100."))
a(yours())
a('<h3>5.5 Chalakudy scenario</h3>' + note("Figures (results/analysis_chalakudy/figures): chalakudy_within_T_by_window, chalakudy_connected_within_T_by_window, chalakudy_over_time_on15_nobatt, chalakudy_sensitivity_acute, chalakudy_within_T_by_window_battery, chalakudy_network_density. Report the propagation result here too: under the cited model no packet was delivered in any of the 90 runs."))
a(yours())

a('<h2>6. Discussion</h2>')
a(note("Yours. Does the evidence support each half of the premise? Separate what the topology and traffic do (visible in the no-flood control) from what flooding does. What does the battery model allow you to say about the sustained phase? How much do the results depend on the 150 m range?"))
a(yours())

a('<h2>7. Limitations</h2>')
a(note("Turn these into prose; each one limits how strongly a result can be read (details: docs/paper-data-guide.md section 5 and experiments/README.md section 7)."))
a(bullets([
    "Unit-disk radio (150 m); under a cited path-loss model the default radio reaches 62.8 m and 100 devices do not form a network.",
    "Static nodes; assumed traffic (no data on disaster message traffic); constant-rate traffic in the main grid.",
    "RTS/CTS off and ns-3 default protocol parameters.",
    "Energy: only the Wi-Fi radio, ns-3 default currents (not a 2018 phone), placeholder battery size; with them devices run flat within hours of the power cut.",
    "Time compression (1 day = 30 s, factor 2,880) for failures and batteries, not for routing and traffic.",
    "Kerala-anchored model: synthetic positions and terrain; assumed flood curve and shares; 27% is a press figure.",
    "Chalakudy: radar cannot see which buildings flooded and missed the peak; ground height is a surface model; the square is nearly flat; buildings are present-day map features (2023-2026), not the 2018 town; one 1 km square; flooded share, devices per building and power-cut date assumed; onset dates from press reports that disagree.",
    "Many tests: some p < 0.05 are expected by chance.",
    "Predictions were not written before the runs, so no result is a blind test of the premise.",
]))
a(yours())

a('<h2>8. Conclusion</h2>')
a(yours())

a('<h2>Acknowledgements and data credits</h2>')
a(note("Required credits: '(c) OpenStreetMap contributors' and 'Overture Maps Foundation' (ODbL); DataMeet (ODbL) for the municipality boundary; Google Open Buildings (licence wording: VERIFY); 'Contains modified Copernicus Sentinel data 2018'; the Copernicus DEM attribution (exact wording: VERIFY on the Copernicus licence page)."))
a(yours())

a('<h2>Data and code availability</h2>')
a(note("Facts you can state: code, inputs, raw simulation outputs and analysis are in the public repository github.com/unknownsoldier1bit/kerala-mesh-simulation (Chalakudy work on branch chalakudy-buildings; update if merged into main). Raw downloads (about 170 MB) are re-fetched by experiments/chalakudy_fetch.py, with URL, access time and SHA-256 in data/chalakudy/downloads.csv; derived files have SHA-256 in data/chalakudy/derived_files.csv. Before submission: add an ODbL notice for the derived data and a licence for the code (the repository has none)."))
a(yours())

a('<h2>References</h2>')
a(note("Check every entry marked VERIFY or NEEDS URL before submission. Add your related-work references."))
a('<ol>' + "".join(f"<li>{r}</li>" for r in [
    "Comptroller and Auditor General of India. Report No. 6 of 2021 (Kerala floods), Chapter III and section 3.5.2. https://cag.gov.in/ag1/kerala/en/audit-report/details/114526",
    "Government of Kerala. Additional Memorandum, 13 September 2018, Table 3, pp. 11-12. https://recovery.preventionweb.net/media/101476/download",
    "KSEB. How KSEBL survived flood 2018. [NEEDS URL and the area the 27 Aug date covers]",
    "Deccan Herald. [Article reporting Chalakudy flooded early 15 Aug 2018: NEEDS URL]",
    "Scroll. [Article quoting an MP that Chalakudy flooded on 17 Aug 2018: NEEDS URL]",
    "TelecomTalk (reporting The Economic Times), 27 Aug 2018: Telecom Secretary's review of Kerala network damage. https://telecomtalk.info/?p=180759 [press]",
    "Perkins, C., Belding-Royer, E., Das, S. Ad hoc On-Demand Distance Vector (AODV) Routing. RFC 3561, 2003. [VERIFY]",
    "Clausen, T., Jacquet, P. Optimized Link State Routing Protocol (OLSR). RFC 3626, 2003. [VERIFY]",
    "Perkins, C. E., Bhagwat, P. Highly dynamic destination-sequenced distance-vector routing (DSDV) for mobile computers. ACM SIGCOMM 1994. [VERIFY]",
    "ns-3 network simulator, version 3.47. https://www.nsnam.org",
    "Overture Maps Foundation. Release 2026-10-21.0. overturemaps.org (accessed 29 Oct 2026)",
    "OpenStreetMap contributors. openstreetmap.org (via Overture)",
    "Sirko, W., et al. Continental-scale building detection from high resolution satellite imagery. arXiv:2107.12283, 2021. [VERIFY]",
    "DataMeet. Indian Village Boundaries, Kerala. github.com/datameet/indian_village_boundaries (accessed 29 Oct 2026)",
    "European Space Agency. Copernicus DEM GLO-30. https://doi.org/10.5270/ESA-c5d3d65 [VERIFY]",
    "European Space Agency. Copernicus Sentinel-1 GRD data, 2018 (AWS Open Data, sentinel-s1-l1c; accessed 29 Oct 2026)",
    "3GPP TR 37.885 V15.3.0 (2019-06). Study on evaluation methodology of new Vehicle-to-Everything (V2X) use cases for LTE and NR, Table 6.2.1-1. [VERIFY]",
    "Otsu, N. A threshold selection method from gray-level histograms. IEEE Trans. Systems, Man, and Cybernetics 9(1):62-66, 1979. [VERIFY]",
    "Friedman, M. The use of ranks to avoid the assumption of normality implicit in the analysis of variance. J. American Statistical Association 32(200):675-701, 1937. [VERIFY]",
    "Wilcoxon, F. Individual comparisons by ranking methods. Biometrics Bulletin 1(6):80-83, 1945. [VERIFY]",
    "Holm, S. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics 6(2):65-70, 1979. [VERIFY]",
]) + '</ol>')

a('<h2>Appendix A. Chalakudy parameters: measured, derived or assumed</h2>')
a(note("Condensed from data/chalakudy/PROVENANCE.md (43 rows there, with sources and reasoning)."))
a(table(["Parameter", "Value", "Kind", "Swept"], [
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
]))

a('<h2>Appendix B. Sentinel-1 scenes</h2>')
a(note("Reference water detected = share of cells inside mapped rivers and ponds classified as water; far land as water = share of land at least 150 m from mapped water classified as water (bounds false detections in dry scenes; on 16 Jul, 9 Aug and 21 Aug part of it may be real flooding)."))
rows = []
for r in s1["per_scene"]:
    rows.append([r["date"], r["time_utc"], r["mission"], f"{r['pass_direction']} {r['relative_orbit']}", f"{r['threshold_db']:.1f}",
                 f"{r['water_share_pct']:.1f}", f"{r['reference_water_detected_pct']:.1f}", f"{r['far_land_detected_as_water_pct']:.2f}"])
a(table(["Date", "Time (UTC)", "Satellite", "Pass, orbit", "Threshold (dB)", "Water (%)", "Reference water detected (%)", "Far land as water (%)"], rows))

a('<h2>Appendix C. Timeline</h2>')
a(table(["Date (2018)", "Event", "Used as", "Source"], [
    ["14-18 Aug", "Dam releases (Idukki shutters opened 10 Aug)", "Water rises until 18 Aug 00:00", "CAG Report No. 6 of 2021, Ch. III"],
    ["15-17 Aug", "IMD red heavy rain, Thrissur", "Same", "Kerala Additional Memorandum, Table 3"],
    ["15 or 17 Aug", "Chalakudy floods", "Onset (both run)", "Deccan Herald; Scroll (NEEDS URL)"],
    ["16 Aug (dam station)", "Communications fail in Chalakudy and Idukki taluks", "Context", "CAG section 3.5.2"],
    ["27 Aug", "Last Thrissur substation back on", "End of run", "KSEB (NEEDS URL)"],
]))
a('</body></html>')
out = "".join(P)
open(f"{REPO}/docs/paper-scaffold.html", "w").write(out)
print(len(out), "bytes")
