"""
Indian APMC market repository sourced from AGMARKNET (data.gov.in).

Loads from a local JSON seed file (backend/data/apmc_markets.json) so the
decision engine never makes repeated calls to a public government endpoint.
The seed file can be refreshed offline via sync_agmarknet.py.

Source: Agricultural Marketing Information Network (AGMARKNET)
        https://agmarknet.gov.in / https://data.gov.in
"""
import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

# Seed file location — relative to this module
_DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "apmc_markets.json"


class MarketRecord(BaseModel):
    """One APMC / agricultural market from the AGMARKNET dataset."""
    market_id: str            # stable slug: "{state_abbr}_{district}_{market}"
    market_name: str          # official registered market name
    state: str                # e.g. "Andhra Pradesh"
    district: str             # e.g. "Krishna"
    market_type: str          # "APMC" | "Wholesale" | "Commission Agent"
    source: str               # "AGMARKNET" | "Manual"
    commodities: List[str]    # [] / ["all"] = unrestricted; otherwise commodity list
    lat: Optional[float] = None
    lng: Optional[float] = None
    active: bool = True


class MarketRepository:
    """
    In-memory repository of real Indian APMC markets.

    All filtering is done in-process over the seed file — no external
    API call at query time.  The repository is populated once at startup
    and re-loaded only when explicitly asked (e.g. after a sync run).
    """

    def __init__(self, data_path: Path = _DEFAULT_DATA_PATH) -> None:
        self._path = data_path
        self._markets: List[MarketRecord] = []
        self.load()

    def load(self) -> None:
        """(Re-)load markets from the JSON seed file."""
        if not self._path.exists():
            self._markets = []
            return
        try:
            raw: list = json.loads(self._path.read_text(encoding="utf-8"))
            self._markets = [
                MarketRecord(**r) for r in raw if r.get("active", True)
            ]
        except Exception:
            self._markets = []

    # ── Query ────────────────────────────────────────────────────────────────

    def search(
        self,
        *,
        state: Optional[str] = None,
        district: Optional[str] = None,
        q: Optional[str] = None,
        commodity: Optional[str] = None,
        limit: int = 50,
    ) -> List[MarketRecord]:
        """
        Filter markets by state, district, free-text search, and commodity.
        All filters are case-insensitive; multiple filters are ANDed.
        """
        results = self._markets

        if state:
            sl = state.strip().lower()
            results = [m for m in results if m.state.lower() == sl]

        if district:
            dl = district.strip().lower()
            results = [m for m in results if m.district.lower() == dl]

        if q:
            ql = q.strip().lower()
            results = [
                m for m in results
                if ql in m.market_name.lower()
                or ql in m.district.lower()
                or ql in m.state.lower()
            ]

        if commodity:
            cl = commodity.strip().lower()
            results = [
                m for m in results
                if not m.commodities
                or any(c.lower() in ("all", cl) for c in m.commodities)
            ]

        return results[:limit]

    def get_by_id(self, market_id: str) -> Optional[MarketRecord]:
        for m in self._markets:
            if m.market_id == market_id:
                return m
        return None

    def all_states(self) -> List[str]:
        return sorted({m.state for m in self._markets})

    def districts_in_state(self, state: str) -> List[str]:
        sl = state.strip().lower()
        return sorted({m.district for m in self._markets if m.state.lower() == sl})

    def count(self) -> int:
        return len(self._markets)


# ── Module-level singleton (one load per process) ─────────────────────────────

_repo: Optional[MarketRepository] = None


def get_repository() -> MarketRepository:
    global _repo
    if _repo is None:
        _repo = MarketRepository()
    return _repo
