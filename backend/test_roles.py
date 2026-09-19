"""
Step 21 & 22 — Farmer/Buyer role and authorization tests.

All Supabase and JWT calls are mocked. No live credentials needed.
"""
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app, _extract_user_id, _require_user_id, _save_to_supabase

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

FARMER_UID = "aaaaaaaa-0000-0000-0000-000000000001"
BUYER_UID  = "bbbbbbbb-0000-0000-0000-000000000002"

def _mock_supabase_with_profile(uid: str, role: str):
    """Return a mock Supabase client that returns a profile row for uid/role."""
    sb = MagicMock()

    # auth.get_user(token) → user with given uid
    user_mock = MagicMock()
    user_mock.id = uid
    auth_resp = MagicMock()
    auth_resp.user = user_mock
    sb.auth.get_user.return_value = auth_resp

    # table("profiles").select(...).eq(...).execute() → existing row
    profile_row = {"id": uid, "role": role, "full_name": "Test User", "created_at": "2026-01-01T00:00:00Z"}
    select_mock = MagicMock()
    select_mock.execute.return_value = MagicMock(data=[profile_row])
    eq_mock = MagicMock()
    eq_mock.execute.return_value = MagicMock(data=[profile_row])
    select_mock.eq.return_value = eq_mock

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[profile_row])

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    table_mock.insert.return_value = insert_mock
    sb.table.return_value = table_mock

    return sb


def _mock_supabase_no_profile(uid: str):
    """Return a mock Supabase client where no profile exists yet."""
    sb = MagicMock()

    user_mock = MagicMock()
    user_mock.id = uid
    auth_resp = MagicMock()
    auth_resp.user = user_mock
    sb.auth.get_user.return_value = auth_resp

    # profiles table returns empty data (no existing profile)
    eq_mock = MagicMock()
    eq_mock.execute.return_value = MagicMock(data=[])
    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    new_row = {"id": uid, "role": "farmer", "full_name": None, "created_at": "2026-01-01T00:00:00Z"}
    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[new_row])

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    table_mock.insert.return_value = insert_mock
    sb.table.return_value = table_mock

    return sb


# ── _extract_user_id ──────────────────────────────────────────────────────────

def test_extract_user_id_none_when_no_header():
    assert _extract_user_id(None) is None


def test_extract_user_id_none_when_malformed():
    assert _extract_user_id("NotBearer token") is None


def test_extract_user_id_returns_uid_when_valid():
    sb = MagicMock()
    user_mock = MagicMock()
    user_mock.id = FARMER_UID
    resp = MagicMock()
    resp.user = user_mock
    sb.auth.get_user.return_value = resp
    with patch("main._get_supabase", return_value=sb):
        uid = _extract_user_id(f"Bearer some-jwt-token")
    assert uid == FARMER_UID


def test_extract_user_id_returns_none_when_supabase_unavailable():
    with patch("main._get_supabase", return_value=None):
        assert _extract_user_id("Bearer token") is None


def test_extract_user_id_returns_none_on_exception():
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("network error")
    with patch("main._get_supabase", return_value=sb):
        assert _extract_user_id("Bearer token") is None


# ── _require_user_id ─────────────────────────────────────────────────────────

def test_require_user_id_raises_401_without_header():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _require_user_id(None)
    assert exc.value.status_code == 401


def test_require_user_id_returns_uid_when_valid():
    sb = MagicMock()
    user_mock = MagicMock()
    user_mock.id = FARMER_UID
    resp = MagicMock()
    resp.user = user_mock
    sb.auth.get_user.return_value = resp
    with patch("main._get_supabase", return_value=sb):
        uid = _require_user_id("Bearer token")
    assert uid == FARMER_UID


# ── GET /api/profile ──────────────────────────────────────────────────────────

def test_get_profile_401_without_auth():
    resp = client.get("/api/profile")
    assert resp.status_code == 401


def test_get_profile_404_when_no_profile_exists():
    sb = _mock_supabase_no_profile(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/profile", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_get_profile_returns_farmer_profile():
    sb = _mock_supabase_with_profile(FARMER_UID, "farmer")
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/profile", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "farmer"
    assert body["id"] == FARMER_UID


def test_get_profile_returns_buyer_profile():
    sb = _mock_supabase_with_profile(BUYER_UID, "buyer")
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/profile", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "buyer"


# ── POST /api/profile ─────────────────────────────────────────────────────────

def test_create_profile_401_without_auth():
    resp = client.post("/api/profile", json={"role": "farmer"})
    assert resp.status_code == 401


def test_create_profile_422_invalid_role():
    sb = _mock_supabase_no_profile(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "admin"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_profile_creates_farmer_role():
    sb = _mock_supabase_no_profile(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "farmer"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert resp.json()["role"] == "farmer"


def test_create_profile_creates_buyer_role():
    sb = _mock_supabase_no_profile(BUYER_UID)
    # Adjust insert to return buyer row
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": BUYER_UID, "role": "buyer", "full_name": None, "created_at": "2026-01-01"}]
    )
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "buyer"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert resp.json()["role"] == "buyer"


def test_create_profile_409_when_already_exists():
    sb = _mock_supabase_with_profile(FARMER_UID, "farmer")
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "buyer"},   # attempting to change role
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ── Role persistence: role is immutable ──────────────────────────────────────

def test_role_cannot_be_changed_via_second_post():
    """Second POST to /api/profile always returns 409 regardless of role sent."""
    sb = _mock_supabase_with_profile(FARMER_UID, "farmer")
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "farmer"},  # same role, still rejected
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ── /api/submission stores user_id ───────────────────────────────────────────

def test_submission_stores_user_id_when_authenticated():
    from main import ProduceInput, OptimizeResponse, PlansResponse, _save_to_supabase

    uid_counter = [0]
    def fake_execute(_self=None):
        uid_counter[0] += 1
        return MagicMock(data=[{"id": f"uuid-{uid_counter[0]:04d}"}])

    insert_mock = MagicMock()
    insert_mock.execute.side_effect = fake_execute
    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    sb = MagicMock()
    sb.table.return_value = table_mock

    data = ProduceInput(
        crop="tomato", quantity_kg=100, quality="Standard",
        farmer_location="Guntur", harvest_date="01/01/2027", shelf_life_days=5,
    )
    # Minimal mock responses
    plan_mock = MagicMock()
    plan_mock.total_quantity_allocated = 100
    plan_mock.total_gross_revenue = 500
    plan_mock.total_transport_cost = 20
    plan_mock.total_spoilage_loss_value = 10
    plan_mock.total_net_value = 470
    plan_mock.allocations = []

    opt_mock = MagicMock()
    opt_mock.recommended = plan_mock

    plans_mock = MagicMock()
    plans_mock.plan_a = plan_mock
    plans_mock.plan_b = plan_mock
    plans_mock.plan_c = plan_mock

    inserted_rows: list = []
    original_insert = table_mock.insert

    def capturing_insert(row):
        inserted_rows.append(row)
        return insert_mock

    table_mock.insert = capturing_insert

    with patch("main._get_supabase", return_value=sb):
        fid = _save_to_supabase(data, opt_mock, plans_mock, user_id=FARMER_UID)

    assert fid is not None
    # First insert is always farmer_inputs
    assert inserted_rows, "No rows were inserted"
    assert inserted_rows[0].get("user_id") == FARMER_UID


def test_submission_works_without_user_id():
    """Unauthenticated submissions still persist (user_id omitted)."""
    from main import ProduceInput, _save_to_supabase

    uid_counter = [0]
    def fake_execute(_self=None):
        uid_counter[0] += 1
        return MagicMock(data=[{"id": f"uuid-{uid_counter[0]:04d}"}])

    insert_mock = MagicMock()
    insert_mock.execute.side_effect = fake_execute
    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    sb = MagicMock()
    sb.table.return_value = table_mock

    data = ProduceInput(
        crop="onion", quantity_kg=200, quality="Premium",
        farmer_location="Vijayawada", harvest_date="01/01/2027", shelf_life_days=7,
    )
    plan_mock = MagicMock()
    plan_mock.total_quantity_allocated = 200
    plan_mock.total_gross_revenue = 1000
    plan_mock.total_transport_cost = 40
    plan_mock.total_spoilage_loss_value = 20
    plan_mock.total_net_value = 940
    plan_mock.allocations = []

    opt_mock = MagicMock(); opt_mock.recommended = plan_mock
    plans_mock = MagicMock()
    plans_mock.plan_a = plans_mock.plan_b = plans_mock.plan_c = plan_mock

    with patch("main._get_supabase", return_value=sb):
        fid = _save_to_supabase(data, opt_mock, plans_mock, user_id=None)

    assert fid is not None
    first_insert_call = sb.table("farmer_inputs").insert.call_args
    inserted_row = first_insert_call[0][0]
    assert "user_id" not in inserted_row


# ── Unauthorized access ───────────────────────────────────────────────────────

def test_get_profile_with_wrong_token_returns_none_uid():
    """If JWT verification fails, user_id is None → 401."""
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("invalid JWT")
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/profile", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401


def test_create_profile_with_wrong_token_returns_401():
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("invalid JWT")
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "farmer"},
            headers={"Authorization": "Bearer bad-token"},
        )
    assert resp.status_code == 401


# ── [Step 27] Buyer access control ───────────────────────────────────────────

def test_buyer_cannot_access_farmer_submissions():
    """A buyer's JWT must not grant access to GET /api/farmer/submissions."""
    sb = _mock_supabase_with_profile(BUYER_UID, "buyer")
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer buyer-token"},
        )
    assert resp.status_code == 403


def test_farmer_can_access_farmer_submissions():
    """A farmer's JWT returns 200 (not 403) from GET /api/farmer/submissions."""
    sb = _mock_supabase_with_profile(FARMER_UID, "farmer")
    # Make farmer_inputs query return empty (no submissions yet)
    inputs_chain = MagicMock()
    inputs_chain.execute.return_value = MagicMock(data=[])
    (sb.table.return_value.select.return_value
       .eq.return_value.order.return_value.limit.return_value) = inputs_chain
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer farmer-token"},
        )
    assert resp.status_code == 200
    assert resp.json()["submissions"] == []


# ── [Step 27] Buyer registration sequence ─────────────────────────────────────

def test_new_user_has_no_profile_before_role_selection():
    """GET /api/profile returns 404 for an authenticated user with no profile yet."""
    sb = _mock_supabase_no_profile(BUYER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/profile", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_buyer_registration_sequence():
    """
    End-to-end buyer registration sequence:
      1. GET /api/profile → 404 (no profile yet)
      2. POST /api/profile {role: buyer} → 201 with buyer profile
      3. GET /api/profile → 200 with role=buyer
    Each step uses its own Supabase mock to simulate sequential state changes.
    """
    # Step 1: No profile exists
    sb_empty = _mock_supabase_no_profile(BUYER_UID)
    with patch("main._get_supabase", return_value=sb_empty):
        resp1 = client.get("/api/profile", headers={"Authorization": "Bearer token"})
    assert resp1.status_code == 404

    # Step 2: Create buyer profile
    sb_create = _mock_supabase_no_profile(BUYER_UID)
    buyer_row = {"id": BUYER_UID, "role": "buyer", "full_name": "Priya Sharma", "created_at": "2026-09-19T08:00:00Z"}
    sb_create.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[buyer_row])
    with patch("main._get_supabase", return_value=sb_create):
        resp2 = client.post(
            "/api/profile",
            json={"role": "buyer", "full_name": "Priya Sharma"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp2.status_code == 201
    assert resp2.json()["role"] == "buyer"
    assert resp2.json()["full_name"] == "Priya Sharma"

    # Step 3: Profile now exists and returns buyer role
    sb_exists = _mock_supabase_with_profile(BUYER_UID, "buyer")
    with patch("main._get_supabase", return_value=sb_exists):
        resp3 = client.get("/api/profile", headers={"Authorization": "Bearer token"})
    assert resp3.status_code == 200
    assert resp3.json()["role"] == "buyer"


def test_buyer_role_is_immutable_after_registration():
    """Once registered as buyer, a second POST cannot change the role."""
    sb = _mock_supabase_with_profile(BUYER_UID, "buyer")
    with patch("main._get_supabase", return_value=sb):
        resp = client.post(
            "/api/profile",
            json={"role": "farmer"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_buyer_registration_requires_auth():
    """POST /api/profile without an Authorization header returns 401."""
    resp = client.post("/api/profile", json={"role": "buyer"})
    assert resp.status_code == 401


def test_buyer_does_not_require_consent():
    """
    Buyers are not blocked by the consent gate.  GET /api/consent returns 404
    (no record) for a buyer without raising any error — the frontend simply
    skips the consent page for non-farmer roles.
    GET /api/consent chain: .select().eq(user_id).eq(version).order().limit().execute()
    """
    sb = _mock_supabase_with_profile(BUYER_UID, "buyer")
    # consent table returns no records (two .eq() calls before .order().limit().execute())
    (sb.table.return_value.select.return_value
       .eq.return_value.eq.return_value
       .order.return_value.limit.return_value
       .execute.return_value) = MagicMock(data=[])
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/consent", headers={"Authorization": "Bearer token"})
    # 404 means no consent record — acceptable for buyers who skip the page
    assert resp.status_code == 404


def test_farmer_privacy_consent_still_required_for_farmers():
    """Farmers without consent get 404 from GET /api/consent (not a 200)."""
    sb = _mock_supabase_with_profile(FARMER_UID, "farmer")
    (sb.table.return_value.select.return_value
       .eq.return_value.eq.return_value
       .order.return_value.limit.return_value
       .execute.return_value) = MagicMock(data=[])
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/consent", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404
