#!/usr/bin/env python3
"""Pull every active for-sale listing in Rabun County, GA from RentCast and
write web/rentcast.json for the map.

- One search covers the whole county (paged 500 at a time).
- Tax/sale records are fetched once per property and cached in
  data/rentcast_cache.json, so later runs only pay for new listings.
- Your hand-entered rows in web/listings.csv that have an address but don't
  match a pulled listing also get a property-record lookup (cached).
- A hard cap on API calls per run (MAX_CALLS) protects your monthly quota.

Env:
  RENTCAST_API_KEY   required
  MAX_CALLS          max API calls this run (default 10)
  MONTHLY_CAP        max API calls per calendar month, across all runs (default 45).
                     Tracked in data/rentcast_cache.json. Keeps you under the
                     free tier's 50 so you can't be billed for overages.
  RENTCAST_BASE      API base URL (default https://api.rentcast.io/v1)
Standard library only, so no pip install is needed.
"""
import csv
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "rentcast.json"
CACHE = ROOT / "data" / "rentcast_cache.json"
MINE = ROOT / "web" / "listings.csv"

BASE = os.environ.get("RENTCAST_BASE", "https://api.rentcast.io/v1").rstrip("/")
KEY = os.environ.get("RENTCAST_API_KEY", "")
MAX_CALLS = int(os.environ.get("MAX_CALLS") or 10)
MONTHLY_CAP = int(os.environ.get("MONTHLY_CAP") or 45)
MONTH = time.strftime("%Y-%m")

# A circle that covers all of Rabun County; results are then filtered by county.
CENTER = (34.88, -83.42)
RADIUS_MI = 17
COUNTY = "rabun"
PAGE = 500

calls = 0


class OutOfCalls(Exception):
    pass


class ApiError(Exception):
    pass


def api(path, **params):
    global calls
    if calls >= MAX_CALLS:
        raise OutOfCalls()
    calls += 1
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"X-Api-Key": KEY, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:  # RentCast returns 404 for "no results"
                return []
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            body = e.read().decode("utf-8", "replace")[:300]
            raise ApiError(f"RentCast error {e.code} on /{path}: {body}")
        except (urllib.error.URLError, OSError) as e:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise ApiError(f"Could not reach RentCast on /{path}: {e}")


def miles(a, b):
    r = math.pi / 180
    h = (math.sin((b[0] - a[0]) * r / 2) ** 2
         + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def latest(d, field):
    """RentCast keys yearly data by year: {"2024": {...}}. Return the newest entry's field."""
    if not isinstance(d, dict) or not d:
        return None, None
    year = max(d, key=lambda k: str(k))
    return year, (d[year] or {}).get(field)


def fetch_listings():
    out, offset = [], 0
    while True:
        page = api("listings/sale", latitude=CENTER[0], longitude=CENTER[1], radius=RADIUS_MI,
                   status="Active", limit=PAGE, offset=offset)
        page = page or []
        out += page
        if len(page) < PAGE:
            return out
        offset += PAGE


def record_for(cache, key, **query):
    """Property record (tax, last sale, features), cached forever by key."""
    if key in cache:
        return cache[key]
    res = api("properties", **query)
    rec = res[0] if isinstance(res, list) and res else (res if isinstance(res, dict) else None)
    cache[key] = rec
    return rec


def slim_record(rec):
    if not rec:
        return {}
    tax_year, tax = latest(rec.get("propertyTaxes"), "total")
    asmt_year, assessed = latest(rec.get("taxAssessments"), "value")
    f = rec.get("features") or {}
    return {
        "tax_year": tax_year, "annual_tax": tax,
        "assessed_year": asmt_year, "assessed_value": assessed,
        "last_sale_date": (rec.get("lastSaleDate") or "")[:10] or None,
        "last_sale_price": rec.get("lastSalePrice"),
        "subdivision": rec.get("subdivision"),
        "parcel_id": rec.get("assessorID"),
        "zoning": rec.get("zoning"),
        "features": {k: v for k, v in {
            "Stories": f.get("floorCount"), "Garage": f.get("garageType") or (f.get("garage") and "Yes"),
            "Garage spaces": f.get("garageSpaces"), "Heating": f.get("heatingType"),
            "Cooling": f.get("coolingType"), "Fireplace": f.get("fireplace") and "Yes",
            "Foundation": f.get("foundationType"), "Roof": f.get("roofType"),
            "Exterior": f.get("exteriorType"), "Pool": f.get("pool") and "Yes",
            "View": f.get("viewType"), "Architecture": f.get("architectureType"),
        }.items() if v},
    }


def slim_listing(l):
    hist = []
    for date, h in sorted((l.get("history") or {}).items(), reverse=True):
        h = h or {}
        hist.append({"date": date[:10], "event": h.get("event"), "price": h.get("price"),
                     "dom": h.get("daysOnMarket")})
    agent, office = l.get("listingAgent") or {}, l.get("listingOffice") or {}
    lot = l.get("lotSize")
    return {
        "id": l.get("id"),
        "address": l.get("formattedAddress"),
        "city": l.get("city"), "zip": l.get("zipCode"), "county": l.get("county"),
        "lat": l.get("latitude"), "lng": l.get("longitude"),
        "property_type": l.get("propertyType"),
        "price": l.get("price"),
        "beds": l.get("bedrooms"), "baths": l.get("bathrooms"),
        "sqft": l.get("squareFootage"), "year_built": l.get("yearBuilt"),
        "lot_sqft": lot, "acres": round(lot / 43560, 2) if lot else None,
        "hoa_fee": (l.get("hoa") or {}).get("fee"),
        "status": l.get("status"), "listing_type": l.get("listingType"),
        "listed_date": (l.get("listedDate") or "")[:10] or None,
        "days_on_market": l.get("daysOnMarket"),
        "mls": " ".join(x for x in [l.get("mlsName"), l.get("mlsNumber")] if x) or None,
        "agent": {k: v for k, v in {"name": agent.get("name"), "phone": agent.get("phone"),
                                     "email": agent.get("email"), "website": agent.get("website")}.items() if v},
        "office": {k: v for k, v in {"name": office.get("name"), "phone": office.get("phone"),
                                      "website": office.get("website")}.items() if v},
        "history": hist[:12],
    }


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def save_cache(cache):
    usage = cache.setdefault("_usage", {})
    usage[MONTH] = usage.get(MONTH, 0) + calls
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))


def main():
    if not KEY:
        sys.exit("Set RENTCAST_API_KEY (in GitHub: Settings > Secrets and variables > Actions).")

    global MAX_CALLS
    cache = load_json(CACHE, {})
    usage = cache.setdefault("_usage", {})
    used_this_month = usage.get(MONTH, 0)
    MAX_CALLS = min(MAX_CALLS, MONTHLY_CAP - used_this_month)
    print(f"{used_this_month} of {MONTHLY_CAP} calls already used in {MONTH}; this run may use {max(MAX_CALLS, 0)}.")
    if MAX_CALLS <= 0:
        print("Monthly cap reached. Nothing to do until next month.")
        return
    previous = {l["id"]: l for l in load_json(OUT, {}).get("listings", [])}
    note = None

    try:
        raw = fetch_listings()
        listings = [slim_listing(l) for l in raw
                    if COUNTY in (l.get("county") or "").lower() and l.get("latitude") and l.get("longitude")]
    except OutOfCalls:
        listings, note = list(previous.values()), "call cap reached during search; kept previous listings"

    # Add tax/sale records, newest listings first, until the call cap runs out.
    listings.sort(key=lambda l: l.get("listed_date") or "", reverse=True)
    skipped = 0
    for l in listings:
        key = f"listing:{l['id']}"
        try:
            rec = record_for(cache, key, address=l["address"]) if l.get("address") else None
        except OutOfCalls:
            rec = None
            skipped += 1
        l["record"] = slim_record(rec or cache.get(key))

    # Your own rows: match to a pulled listing within ~200 ft, else look up the address.
    mine = {}
    if MINE.exists():
        with MINE.open(newline="") as f:
            for row in csv.DictReader(f):
                lid = (row.get("listing_id") or "").strip()
                if not lid or lid.startswith("EX-"):
                    continue
                try:
                    pt = (float(row["lat"]), float(row["lng"]))
                except (KeyError, ValueError):
                    continue
                match = next((l for l in listings if miles(pt, (l["lat"], l["lng"])) < 0.04), None)
                if match:
                    mine[lid] = {"rentcast_id": match["id"]}
                    continue
                addr = (row.get("address") or "").strip()
                if addr and "EXAMPLE" not in addr:
                    try:
                        rec = record_for(cache, f"mine:{addr.lower()}", address=addr)
                    except OutOfCalls:
                        rec, skipped = cache.get(f"mine:{addr.lower()}"), skipped + 1
                    if rec:
                        mine[lid] = {"record": slim_record(rec)}

    save_cache(cache)
    OUT.write_text(json.dumps({
        "updated": time.strftime("%Y-%m-%d"),
        "source": "RentCast",
        "note": note,
        "records_pending": skipped,
        "listings": listings,
        "mine": mine,
    }, indent=1))
    print(f"{len(listings)} Rabun listings, {len(mine)} of yours enriched, "
          f"{calls} API calls used, {skipped} records left for next run.")


if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        # Still record the calls we spent, so the monthly cap stays accurate.
        c = load_json(CACHE, {})
        save_cache(c)
        sys.exit(str(e))
