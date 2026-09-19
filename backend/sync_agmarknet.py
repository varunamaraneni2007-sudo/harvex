"""
AGMARKNET sync script — fetches unique market records from data.gov.in and
writes them to backend/data/apmc_markets.json.

Usage:
    AGMARKNET_API_KEY=<your-key> python sync_agmarknet.py [--state "Andhra Pradesh"]

A free API key is available at: https://data.gov.in/user/register
Dataset: AGMARKNET daily commodity prices
  https://data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070

The script deduplicates on (state, district, market) and merges new records
into the existing seed file without removing already-known entries.

Records are written to:  backend/data/apmc_markets.json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    print("httpx is required: pip install httpx", file=sys.stderr)
    sys.exit(1)

DATA_PATH = Path(__file__).parent / "data" / "apmc_markets.json"
AGMARKNET_API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
PAGE_SIZE = 500
REQUEST_DELAY_S = 0.5          # be polite to the public API
MAX_PAGES = 100                # safety ceiling


def _slug(text: str) -> str:
    """Convert a string to a stable URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _make_market_id(state: str, district: str, market: str) -> str:
    state_abbr = {
        "andhra pradesh": "ap", "telangana": "tg", "maharashtra": "mh",
        "karnataka": "ka", "punjab": "pb", "haryana": "hr",
        "uttar pradesh": "up", "rajasthan": "rj", "madhya pradesh": "mp",
        "gujarat": "gj", "west bengal": "wb", "tamil nadu": "tn",
        "odisha": "or", "bihar": "br", "chhattisgarh": "cg",
        "jharkhand": "jh", "uttarakhand": "uk", "himachal pradesh": "hp",
        "jammu and kashmir": "jk", "assam": "as", "kerala": "kl",
        "goa": "ga",
    }.get(state.lower(), _slug(state)[:3])
    return f"{state_abbr}_{_slug(district)}_{_slug(market)}"


def fetch_records(
    api_key: str,
    state_filter: Optional[str] = None,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """Page through the AGMARKNET API and return all raw records."""
    all_records: List[Dict[str, Any]] = []
    params: Dict[str, Any] = {
        "api-key": api_key,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": 0,
    }
    if state_filter:
        params["filters[state]"] = state_filter

    for page in range(MAX_PAGES):
        params["offset"] = page * PAGE_SIZE
        try:
            resp = httpx.get(AGMARKNET_API_URL, params=params, timeout=15.0)
            resp.raise_for_status()
        except Exception as exc:
            print(f"  Error on page {page}: {exc}", file=sys.stderr)
            break

        data = resp.json()
        records = data.get("records", [])
        if not records:
            break

        all_records.extend(records)
        count = data.get("count", len(all_records))
        if verbose:
            print(f"  Fetched page {page + 1}: {len(records)} records"
                  f" ({len(all_records)} / {count} total)")

        if len(all_records) >= count:
            break

        time.sleep(REQUEST_DELAY_S)

    return all_records


def deduplicate_to_markets(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract unique (state, district, market) triples from raw AGMARKNET records.
    No prices or quantities are retained — Step 19 handles live pricing.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for r in records:
        state = (r.get("state") or "").strip().title()
        district = (r.get("district") or "").strip().title()
        market = (r.get("market") or "").strip().title()
        if not (state and district and market):
            continue
        mid = _make_market_id(state, district, market)
        if mid not in seen:
            seen[mid] = {
                "market_id": mid,
                "market_name": market,
                "state": state,
                "district": district,
                "market_type": "APMC",
                "source": "AGMARKNET",
                "commodities": ["all"],
                "lat": None,
                "lng": None,
                "active": True,
            }
    return list(seen.values())


def merge_into_seed(new_markets: List[Dict[str, Any]], seed_path: Path) -> int:
    """
    Merge new_markets into the existing seed file without removing old entries.
    Returns the number of newly added records.
    """
    existing: Dict[str, Dict[str, Any]] = {}
    if seed_path.exists():
        try:
            for m in json.loads(seed_path.read_text(encoding="utf-8")):
                existing[m["market_id"]] = m
        except Exception:
            pass

    added = 0
    for m in new_markets:
        if m["market_id"] not in existing:
            existing[m["market_id"]] = m
            added += 1

    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(
        json.dumps(sorted(existing.values(), key=lambda x: x["market_id"]),
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync AGMARKNET market records")
    parser.add_argument(
        "--state", default=None,
        help='Limit fetch to one state, e.g. "Andhra Pradesh"',
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print discovered markets without writing")
    args = parser.parse_args()

    api_key = os.getenv("AGMARKNET_API_KEY", "")
    if not api_key:
        print(
            "Error: set AGMARKNET_API_KEY environment variable.\n"
            "Free registration at https://data.gov.in/user/register",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Fetching from AGMARKNET API{' (state=' + args.state + ')' if args.state else ''}…")
    records = fetch_records(api_key, state_filter=args.state)
    print(f"Total raw records fetched: {len(records)}")

    markets = deduplicate_to_markets(records)
    print(f"Unique markets extracted:  {len(markets)}")

    if args.dry_run:
        for m in markets[:20]:
            print(f"  {m['market_id']:50s}  {m['market_name']} ({m['district']}, {m['state']})")
        if len(markets) > 20:
            print(f"  … and {len(markets) - 20} more")
        return

    added = merge_into_seed(markets, DATA_PATH)
    print(f"Seed file updated: {added} new markets added → {DATA_PATH}")


if __name__ == "__main__":
    main()
