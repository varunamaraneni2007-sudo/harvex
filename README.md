# Harvex

**Farm-to-Value decision platform for Indian farmers.**

Harvex helps farmers decide where and how to sell their produce by combining real AGMARKNET mandi price data, road-distance logistics, and an LP-based allocation engine to recommend the optimal split across markets — with Plan A/B/C scenarios and what-if analysis.

---

## Implemented Features (Steps 1–36)

| Steps | Feature |
|---|---|
| 1–13 | Core decision engine: LP optimizer (OR-Tools GLOP), greedy allocator, quality multipliers, spoilage model, Plan A/B/C, what-if simulator, explain service |
| 14 | Quality eligibility bug fix |
| 15–16 | Structured crop selector with category browser |
| 17 | Google Places location selector (server-side key proxy) |
| 18 | Real APMC market discovery from AGMARKNET (110 markets) |
| 19 | Live mandi price layer via AGMARKNET price service |
| 20 | Supabase authentication (email/password) |
| 21–22 | Farmer/Buyer role system with Supabase RLS |
| 23 | Farmer privacy and consent gate |
| 24 | Farmer profile page (view/edit) |
| 25 | Farmer dashboard with recent submissions |
| 26 | Persistent farmer data with ownership isolation |
| 27–31 | Buyer system: registration, profile, requirements CRUD, validation, persistence |
| 32–36 | Generalized decision engine: data-driven crops, markets, farmer locations, live prices |

---

## Technology Stack

**Backend**
- Python 3.11, FastAPI, Pydantic v2
- OR-Tools GLOP linear solver (allocation optimizer)
- Supabase (PostgreSQL + Auth) — service_role key, backend-only
- Google Maps Routes API + Places API (New) — backend-only proxy
- AGMARKNET price data (live mandi prices)
- Anthropic API (optional — AI-generated allocation explanations)

**Frontend**
- React 18, TypeScript, Vite 5
- Tailwind CSS
- Supabase Auth v2 (anon key only)
- Vitest 2 (unit tests)

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project with the schema from `backend/schema.sql`

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and fill in your credentials (see Environment Variables below)
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Edit .env.local and fill in your Supabase values
npm run dev
```

The frontend dev server proxies `/api/*` to `http://localhost:8000`.

### Tests

```bash
# Backend
cd backend && python -m pytest

# Frontend
cd frontend && npm test
```

---

## Environment Variables

### Backend — `backend/.env`

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Project URL from Supabase Dashboard → Project Settings → API |
| `SUPABASE_SERVICE_KEY` | Yes | `service_role` key (never expose to browser). Used to read/write user data server-side. |
| `GOOGLE_MAPS_API_KEY` | No | Backend-only API key with Routes API + Places API (New) enabled. Leave blank to use static transport-cost fallback. |
| `ANTHROPIC_API_KEY` | No | API key for AI-generated allocation explanations. Leave blank for deterministic fallback. |

### Frontend — `frontend/.env.local`

| Variable | Required | Description |
|---|---|---|
| `VITE_SUPABASE_URL` | Yes | Same project URL as above |
| `VITE_SUPABASE_ANON_KEY` | Yes | Public `anon` key only — **never** use the service_role key here |

> **Security:** `backend/.env` and `frontend/.env.local` are git-ignored. Never commit real credentials. The service_role key must never reach the browser.

---

## Market Catalogue

The engine's market catalogue lives in `backend/data/markets.json`. Add, remove, or edit markets there without touching application code. Each entry requires:

```json
{
  "market_name": "...",
  "location": "...",
  "base_price_per_kg": 0.0,
  "transport_cost_per_kg": 0.0,
  "capacity_kg": 0.0,
  "base_spoilage_pct": 0.0,
  "buyer_type": "...",
  "accepted_crops": ["all"],
  "min_quality": "Low"
}
```

Live AGMARKNET mandi prices automatically overlay `base_price_per_kg` at request time when a matching price record exists for the crop.
