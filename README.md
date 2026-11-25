# Land Scout

A simple map of land and houses for sale in Rabun County, GA. Everything is in `web/`.

## Run it

```bash
cd web && python3 -m http.server 8000
```

Open http://localhost:8000 (or on your phone, at your computer's IP address on port 8000).

## Add a listing

Add a row to `web/listings.csv` and reload the page.

| column | example | notes |
|---|---|---|
| listing_id | RAB-001 | any unique ID |
| url | https://... | link to the listing |
| source | zillow | |
| status | active | |
| price | 325000 | plain number |
| acres | 4.2 | |
| beds, baths, sqft, year_built | 3, 2, 1650, 1998 | leave blank for land only |
| lat, lng | 34.8805, -83.3990 | required. In Google Maps, right-click the spot and click the numbers to copy them |
| drive_min_atl | 105 | optional. Use the "Directions to ATL" button to look it up |
| address | 123 Main St | shown as the card title |
| notes | ... | put quotes around notes that contain commas |

The two `EX-` rows are fake sample rows. Delete them.

**Parcel outline (optional):** draw the parcel at geojson.io, then copy the feature into `web/boundaries.geojson` with `"listing_id"` set in `properties`.

## All Rabun listings, from RentCast

A GitHub Action (`.github/workflows/enrich.yml`) runs every Monday. It pulls every active for-sale home and land listing in Rabun County from the [RentCast](https://www.rentcast.io/api) API into `web/rentcast.json`, then redeploys the site. Each listing card then shows type, lot size, HOA, listed date, days on market, MLS number, listing agent and office (tap to call or email), price history, assessed value, property tax, last sale, parcel ID, and home features.

One-time setup:

1. Sign up at rentcast.io and create an API key.
2. In GitHub, go to the repo's **Settings → Secrets and variables → Actions**. Add a secret named `RENTCAST_API_KEY` with the key.
3. Go to **Actions → Pull Rabun listings (RentCast) → Run workflow** to run it now instead of waiting for Monday.

**API calls:** one search covers the whole county. After that, each listing costs one call for its tax and sale record, the first time only, because records are cached in `data/rentcast_cache.json`. Each run stops at `MAX_CALLS` (default 10). There is also a hard monthly cap, `MONTHLY_CAP` (default 45), counted across all runs including manual ones and failed calls, so the job can never go past the free tier's 50 a month. Records for remaining listings fill in on later runs. On a paid plan, set repo **variables** `MAX_CALLS` and `MONTHLY_CAP` to fit your plan (for example 500 and 950) under Settings → Secrets and variables → Actions → Variables, and everything fills in on the first run.

Your own rows in `listings.csv` are matched to a RentCast listing at the same spot. If there isn't one, the script looks up the `address` instead. What you typed by hand always wins. Listings you added yourself have a blue ring on the map.

## What's on the map

- Satellite or USGS topo base map, with hillshade
- Roads and road names, streams and lakes, towns, mountain peaks with elevations, places (stores, churches, trailheads), public land and national forest, building outlines, the county line, and contour lines (from OpenStreetMap and USGS)
- Slope (USGS 3DEP) and FEMA flood zones, which you can turn on and off
- Tap any spot on the map for its elevation, FEMA flood zone, whether it's public land, the nearest road and water, and straight-line miles to Clayton and Atlanta. Listing cards show the same site info
- Listings: red = house, yellow = land only, with price labels
- Tap a listing for price, acres, $/acre, beds and baths, sq ft, $/sq ft, year built, drive time, and links to the listing, directions to Atlanta, the county parcel record (qPublic), and FEMA's flood map
- Filters: max price, min acres, min beds, has a house

The map layers come live from public Esri, USGS, and FEMA servers. No API keys are needed.

Use this for screening only. Confirm boundaries, flood zone, and buildability with the county, a survey, and a perc test before you buy.

## Host it free

Push the repo, then turn on GitHub Pages or Cloudflare Pages, using `web/` as the site folder.
