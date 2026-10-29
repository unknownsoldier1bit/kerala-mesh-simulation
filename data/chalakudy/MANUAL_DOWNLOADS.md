# Files to download by hand

This cloud session cannot reach these sites. Every one failed on 29 Oct 2026 between 06:40 and 07:12 UTC with the same error from the session's network proxy, `curl: (56) CONNECT tunnel failed, response 403`, and the WebFetch tool failed for the same hosts with `getaddrinfo ENOTFOUND`. Nothing below has been substituted with a guess: where a value is needed before these arrive, it is marked ASSUMED or "pending" in `PROVENANCE.md`.

How to hand them over: put each file in `data/chalakudy/manual/` (create the folder), keep the original file name, and note in this file where you got it and on what date. Large files (over about 50 MB) shouldn't be committed; tell the session where they are instead.

## Needed (the scenario depends on these)

| # | What | Exact file and where | Why it's needed |
|---|---|---|---|
| 1 | Chalakudy (M) 2011 census: population and number of households | Best: Census of India 2011, District Census Handbook, Thrissur, Part B (Village and Town-wise Primary Census Abstract), the row for town "Chalakudy (M)", from censusindia.gov.in. Easier alternative: AMRUT Kerala, City Water Balance Plan, Chalakudy, https://amrutkerala.org/wp-content/uploads/2022/06/CWBP_CHALAKUDY-M.pdf | People per building and devices per building. Search snippets give 49,525 people and 12,218 or 12,567 households, but neither source could be opened, so they are not used as measured values |
| 2 | Mobile-phone ownership in Kerala around 2018 | NFHS-5 (2019–21) Kerala State Fact Sheet from rchiips.org (indicator "Women having a mobile phone that they themselves use"), and/or TRAI "Highlights of Telecom Subscription Data as on 31st July 2018" (or August 2018) press release from trai.gov.in, which gives the Kerala circle's teledensity | Devices per person |
| 3 | Chalakudy River water levels in August 2018 | Central Water Commission, "Study Report: Kerala Floods of August 2018" (September 2018). Listing: https://www.preventionweb.net/publication/study-report-kerala-floods-august-2018 (the PDF link there was already dead on 12 Oct); otherwise cwc.gov.in. Needed: the hydrograph or table for the Arangali gauge on the Chalakudy River | The time and height of the flood peak in Chalakudy. Sentinel-1 has no image between 10 and 20 Aug, so the peak water level and its timing are currently ASSUMED and swept. This report could settle the "15 vs 17 Aug" onset question too |
| 4 | KSEB, "How KSEBL survived flood 2018" | kseb.in (search the site for the title) | When power was cut in the Chalakudy/Thrissur area (only the restoration dates are verified so far). Decides when devices stop recharging |

## Useful (cross-checks and context)

| # | What | Where | Why |
|---|---|---|---|
| 5 | Dartmouth Flood Observatory, event 4663 (2018 India): flood-extent shapefiles | https://floodobservatory.colorado.edu/Events/4663/2018India4663.html (the page reportedly links Sentinel-1-based shapefiles) | Independent check of the flood map made here from Sentinel-1 |
| 6 | Tiwari et al. 2020, PLoS ONE 15(8): e0237324, full text | https://doi.org/10.1371/journal.pone.0237324 | Compare their 21 Aug flood extent and method around Chalakudy |
| 7 | A cited typical smartphone battery capacity for India, 2018 | For example, a market report listing India's best-selling phones in 2018 plus the manufacturers' spec sheets for those models | Battery size of a mesh device. Until then it is ASSUMED and swept |
| 8 | FABDEM bare-earth elevation, tile N10E076 | University of Bristol data repository, https://data.bris.ac.uk/data/dataset/s5hqmjcdj8yo2ibzi9b4ew3sn (the 10°×10° zip containing N10E076) | The Copernicus DEM used now is a surface model (includes trees and roofs). FABDEM removes them, which matters for deciding which buildings are lowest |
| 9 | Cell-tower locations around Chalakudy | OpenCelliD (opencellid.org; needs a free account and API key) | Optional context only |

## Can't be fetched from here, and not needed now

- Ward boundaries for Chalakudy (36 wards per search snippets): OpenStreetMap is blocked. The whole-municipality boundary from DataMeet (ODbL) is used instead.
