# Kerala 2018 data sources

Status as of 12 Oct 2026, after opening the documents. Of the 13 things the failure model needs, 6 are verified, 3 are partial and 4 are missing.

## Verified

| Need | What's documented | Source |
|---|---|---|
| Daily rainfall, Thrissur | Heavy rain (IMD "red") on 15, 16 and 17 Aug; 414 mm statewide over those 3 days | Govt of Kerala, Additional Memorandum (13 Sep 2018), Table 3 p. 11 and p. 12 |
| Dam releases | 14–18 Aug; Idukki shutters opened 10 Aug | CAG Report No. 6 of 2021, Chapter III |
| Communications failure near Chalakudy | Chalakudy and Idukki taluks: total failure. Poringalkuthu dam: down 16 Aug, restored about a week later | CAG Report No. 6 of 2021, §3.5.2 |
| Power outage and restoration | 25.60 lakh consumers cut off; 16,158 distribution transformers affected; last Thrissur substation back 27 Aug; 99.9% restored by 1 Sep | KSEB, "How KSEBL survived flood 2018" |
| Statewide telecom damage | 23,552 of 85,900 base stations (~27%); 190 fibre cuts; 400+ sites on diesel | Telecom Secretary review, reported by ET via TelecomTalk, 27 Aug 2018 (press only) |
| When Chalakudy flooded | Early 15 Aug (Deccan Herald) vs 17 Aug (Scroll, quoting an MP) | Sources disagree |

## Partial

- **Flood extent.** Available only as images: memorandum Figure 4 (NRSC radar, 65,188 ha), Tiwari et al. 2020 (PLoS ONE, Sentinel-1, 9 and 21 Aug, 10 m), Vishnu et al. 2019 (includes Thrissur). No downloadable map file confirmed.
- **Flood-prone zones.** NCESS map in the 2016 State Disaster Management Plan; KSDMA holds the GIS files.
- **Tower locations.** Crowdsourced only (OpenCelliD).

## Missing (become swept parameters or stated assumptions)

- Tower battery runtime: no official figure. Sweep it (e.g. 2–12 h).
- Hour-by-hour outage timeline: build from the anchor dates above.
- Data for individual towers: not published. Use ~27% statewide as a floor and "total failure" at Chalakudy as a ceiling.
- Message traffic during the disaster: assume bursty on/off traffic and sweep the rate.

## Links

- Memorandum: https://recovery.preventionweb.net/media/101476/download (blocks scripts; open in a browser)
- CAG report: https://cag.gov.in/ag1/kerala/en/audit-report/details/114526
- KSEB: search kseb.in for "How KSEBL survived flood 2018"
- TelecomTalk: https://telecomtalk.info/?p=180759
- Tiwari et al. 2020: https://doi.org/10.1371/journal.pone.0237324
- Vishnu et al. 2019: https://doaj.org/article/5e2f8aa52e024de483ec6e800bcc6e10
- CWC study report listing (PDF link currently dead): https://www.preventionweb.net/publication/study-report-kerala-floods-august-2018

## Don't cite (no source found)

~300 Kerala towers down, 4–8 h tower batteries, Nepal ~90%, Maria ~95%, Haiti ~60%. Death tolls vary by source (339 / 433 / 474 / 483); pick one and name it.
