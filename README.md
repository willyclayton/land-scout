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

## What's on the map

- Satellite or USGS topo base map, with hillshade
- Slope (USGS 3DEP) and FEMA flood zones, which you can turn on and off
- Listings: red = house, yellow = land only, with price labels
- Tap a listing for price, acres, $/acre, beds and baths, sq ft, $/sq ft, year built, drive time, and links to the listing, directions to Atlanta, the county parcel record (qPublic), and FEMA's flood map
- Filters: max price, min acres, min beds, has a house

The map layers come live from public Esri, USGS, and FEMA servers. No API keys are needed.

Use this for screening only. Confirm boundaries, flood zone, and buildability with the county, a survey, and a perc test before you buy.

## Host it free

Push the repo, then turn on GitHub Pages or Cloudflare Pages, using `web/` as the site folder.
