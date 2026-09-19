"""
AGMARKNET mandi price service.

Fetches current wholesale (mandi) prices from the AGMARKNET dataset on
data.gov.in and caches them locally.

API dataset: 9ef84268-d588-465a-a308-a864a43d0070
AGMARKNET reports prices in rupees per quintal (1 quintal = 100 kg).
All prices stored and returned are rupees per kg.

Refresh the local cache with:
    AGMARKNET_API_KEY=<key> python -c \
        "from price_service import refresh_price_cache; refresh_price_cache(verbose=True)"

Or filter to a single commodity:
    AGMARKNET_API_KEY=<key> python -c \
        "from price_service import refresh_price_cache; refresh_price_cache(commodity_filter='Tomato')"
"""

import json
import re
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

_DEFAULT_CACHE_PATH = Path(__file__).parent / "data" / "price_cache.json"
AGMARKNET_API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
PAGE_SIZE = 500
_QUINTAL_TO_KG = 100.0


# ── ID slug helpers (mirrors sync_agmarknet.py) ───────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


_STATE_ABBR: Dict[str, str] = {
    "andhra pradesh": "ap", "telangana": "tg", "maharashtra": "mh",
    "karnataka": "ka", "punjab": "pb", "haryana": "hr",
    "uttar pradesh": "up", "rajasthan": "rj", "madhya pradesh": "mp",
    "gujarat": "gj", "west bengal": "wb", "tamil nadu": "tn",
    "odisha": "or", "bihar": "br", "chhattisgarh": "cg",
    "jharkhand": "jh", "uttarakhand": "uk", "himachal pradesh": "hp",
    "jammu and kashmir": "jk", "assam": "as", "kerala": "kl",
    "goa": "ga",
}


def _make_market_id(state: str, district: str, market: str) -> str:
    abbr = _STATE_ABBR.get(state.lower(), _slug(state)[:3])
    return f"{abbr}_{_slug(district)}_{_slug(market)}"


# ── Price model ───────────────────────────────────────────────────────────────

class PriceRecord(BaseModel):
    """One mandi price record from AGMARKNET."""
    market_id: str                          # slug matching MarketRecord.market_id
    market_name: str                        # as reported by AGMARKNET
    state: str
    district: str
    commodity: str
    variety: Optional[str] = None
    grade: Optional[str] = None
    min_price_per_kg: Optional[float] = None
    modal_price_per_kg: Optional[float] = None
    max_price_per_kg: Optional[float] = None
    unit: str = "kg"                        # always "kg" after conversion
    price_date: Optional[str] = None        # "DD/MM/YYYY" from AGMARKNET
    source: str = "AGMARKNET"


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_price(val) -> Optional[float]:
    """Convert a price string in rupees/quintal to rupees/kg."""
    try:
        return round(float(str(val).replace(",", "").strip()) / _QUINTAL_TO_KG, 2)
    except (ValueError, TypeError):
        return None


def _date_key(date_str: Optional[str]) -> str:
    """Convert DD/MM/YYYY → YYYY/MM/DD for lexicographic chronological sort."""
    if not date_str:
        return ""
    parts = date_str.split("/")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return date_str


def raw_to_price_record(r: dict) -> Optional[PriceRecord]:
    """Convert one raw AGMARKNET API record to a PriceRecord, or None if invalid."""
    state = (r.get("state") or "").strip().title()
    district = (r.get("district") or "").strip().title()
    market = (r.get("market") or "").strip().title()
    commodity = (r.get("commodity") or "").strip().title()
    if not (state and district and market and commodity):
        return None
    variety = (r.get("variety") or "").strip().title() or None
    grade = (r.get("grade") or "").strip().upper() or None
    return PriceRecord(
        market_id=_make_market_id(state, district, market),
        market_name=market,
        state=state,
        district=district,
        commodity=commodity,
        variety=variety,
        grade=grade,
        min_price_per_kg=_parse_price(r.get("min_price")),
        modal_price_per_kg=_parse_price(r.get("modal_price")),
        max_price_per_kg=_parse_price(r.get("max_price")),
        price_date=r.get("arrival_date") or None,
    )


# ── Repository ────────────────────────────────────────────────────────────────

class PriceRepository:
    """
    In-memory repository of AGMARKNET mandi prices.

    Prices are loaded from a local JSON cache file populated by
    refresh_price_cache() or the /api/market-prices/refresh endpoint.
    When the cache is absent (no API key configured) the repository is empty
    and the endpoint returns an informative empty response.
    """

    def __init__(self, cache_path: Path = _DEFAULT_CACHE_PATH) -> None:
        self._path = cache_path
        self._records: List[PriceRecord] = []
        self._fetched_at: Optional[float] = None
        self.load()

    def load(self) -> None:
        """(Re-)load from the cache file."""
        if not self._path.exists():
            self._records = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._fetched_at = data.get("fetched_at")
            self._records = [PriceRecord(**r) for r in data.get("records", [])]
        except Exception:
            self._records = []

    def count(self) -> int:
        return len(self._records)

    def cache_age_hours(self) -> Optional[float]:
        if self._fetched_at is None:
            return None
        return round((time.time() - self._fetched_at) / 3600, 1)

    def search(
        self,
        *,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        latest: bool = True,
        limit: int = 50,
    ) -> List[PriceRecord]:
        """
        Filter price records.  All string filters are case-insensitive.
        latest=True keeps only the most recent record per
        (state, district, market, commodity) combination.
        """
        results = self._records

        if commodity:
            cl = commodity.strip().lower()
            results = [r for r in results if cl in r.commodity.lower()]

        if state:
            sl = state.strip().lower()
            results = [r for r in results if r.state.lower() == sl]

        if district:
            dl = district.strip().lower()
            results = [r for r in results if r.district.lower() == dl]

        if market:
            ml = market.strip().lower()
            results = [r for r in results if ml in r.market_name.lower()]

        if latest:
            best: Dict[Tuple, PriceRecord] = {}
            for r in results:
                key = (r.state, r.district, r.market_name, r.commodity)
                if key not in best or _date_key(r.price_date) > _date_key(best[key].price_date):
                    best[key] = r
            results = list(best.values())

        return results[:limit]


# ── Live-fetch helpers ────────────────────────────────────────────────────────

def fetch_live_prices(
    api_key: str,
    commodity_filter: Optional[str] = None,
    state_filter: Optional[str] = None,
    max_pages: int = 20,
    verbose: bool = False,
) -> List[dict]:
    """Page through the AGMARKNET API and return raw records."""
    try:
        import httpx
    except ImportError:
        return []

    all_records: List[dict] = []
    params: Dict = {
        "api-key": api_key,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": 0,
    }
    if commodity_filter:
        params["filters[commodity]"] = commodity_filter
    if state_filter:
        params["filters[state]"] = state_filter

    for page in range(max_pages):
        params["offset"] = page * PAGE_SIZE
        try:
            resp = httpx.get(AGMARKNET_API_URL, params=params, timeout=15.0)
            resp.raise_for_status()
        except Exception as exc:
            if verbose:
                print(f"  Error on page {page}: {exc}")
            break
        data = resp.json()
        records = data.get("records", [])
        if not records:
            break
        all_records.extend(records)
        count = data.get("count", len(all_records))
        if verbose:
            print(f"  Page {page + 1}: {len(records)} records ({len(all_records)}/{count})")
        if len(all_records) >= count:
            break
        time.sleep(0.5)

    return all_records


def refresh_price_cache(
    api_key: str = "",
    commodity_filter: Optional[str] = None,
    state_filter: Optional[str] = None,
    cache_path: Path = _DEFAULT_CACHE_PATH,
    verbose: bool = True,
) -> int:
    """
    Fetch current prices from AGMARKNET and write to the local cache.
    Returns the number of PriceRecords stored.
    Existing cache is merged (new records for same market+commodity+date
    replace old ones; other records are kept).
    """
    key = api_key or os.getenv("AGMARKNET_API_KEY", "")
    if not key:
        if verbose:
            print("No AGMARKNET_API_KEY configured — cache not updated.")
        return 0

    if verbose:
        print(f"Fetching prices from AGMARKNET API"
              f"{' (commodity=' + commodity_filter + ')' if commodity_filter else ''}"
              f"{' (state=' + state_filter + ')' if state_filter else ''}…")
    raw = fetch_live_prices(key, commodity_filter=commodity_filter,
                            state_filter=state_filter, verbose=verbose)
    if verbose:
        print(f"Raw records fetched: {len(raw)}")

    # Load existing cache to merge into
    existing: Dict[str, dict] = {}
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            for r in data.get("records", []):
                # Deduplicate on (market_id, commodity, price_date)
                k = f"{r.get('market_id','')}/{r.get('commodity','')}/{r.get('price_date','')}"
                existing[k] = r
        except Exception:
            pass

    added = 0
    for raw_r in raw:
        pr = raw_to_price_record(raw_r)
        if pr is None:
            continue
        k = f"{pr.market_id}/{pr.commodity}/{pr.price_date or ''}"
        if k not in existing:
            added += 1
        existing[k] = pr.model_dump()

    records = list(existing.values())
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"fetched_at": time.time(), "records": records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if verbose:
        print(f"Cache updated: {added} new records → {cache_path}  (total {len(records)})")
    return len(records)


# ── Module-level singleton ────────────────────────────────────────────────────

_price_repo: Optional[PriceRepository] = None


def get_price_repository() -> PriceRepository:
    global _price_repo
    if _price_repo is None:
        _price_repo = PriceRepository()
    return _price_repo
