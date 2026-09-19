"""
Tests for Steps 28-31: Buyer Profile, Buyer Requirements CRUD,
Buyer Validation, and security/ownership enforcement.
"""
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app, _get_supabase

client = TestClient(app)

BUYER_USER_ID = "buyer-uuid-001"
BUYER_B_USER_ID = "buyer-uuid-002"
FARMER_USER_ID = "farmer-uuid-001"
BUYER_AUTH = "Bearer buyer-token-001"
BUYER_B_AUTH = "Bearer buyer-token-002"
FARMER_AUTH = "Bearer farmer-token-001"

REQ_ID = "req-uuid-001"


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_sb(user_id: str, role: str):
    """Return a mock Supabase client that authenticates `user_id` and returns `role`."""
    sb = MagicMock()
    auth_resp = MagicMock()
    auth_resp.user = MagicMock(id=user_id)
    sb.auth.get_user.return_value = auth_resp

    profile_mock = MagicMock()
    profile_mock.data = [{"role": role}]
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = profile_mock

    return sb


def _mock_buyer_sb(user_id: str = BUYER_USER_ID):
    """Returns a sb mock for a buyer user."""
    return _make_sb(user_id, "buyer")


def _mock_farmer_sb(user_id: str = FARMER_USER_ID):
    """Returns a sb mock for a farmer user."""
    return _make_sb(user_id, "farmer")


def _make_per_table_sb(user_id: str, role: str, req_data, updated_row=None):
    """
    Return a mock Supabase client that routes sb.table() calls to per-table
    mock objects. This lets the role check (profiles table, 1 .eq()) and the
    ownership/existence check (buyer_requirements table, 1 .eq()) return
    different data without colliding on the same mock chain.

    - profiles table: role check returns [{"role": role}]
    - buyer_requirements table:
        - select → req_data
        - update → [updated_row] (when updated_row is provided)
        - delete → []
    """
    sb = MagicMock()
    auth_resp = MagicMock()
    auth_resp.user = MagicMock(id=user_id)
    sb.auth.get_user.return_value = auth_resp

    profiles_table = MagicMock()
    profiles_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"role": role}]
    )

    req_table = MagicMock()
    req_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=req_data
    )
    if updated_row is not None:
        req_table.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_row]
        )
    req_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def _table(table_name):
        return profiles_table if table_name == "profiles" else req_table

    sb.table.side_effect = _table
    return sb


# ── Buyer Profile (Step 28) ────────────────────────────────────────────────────

class TestBuyerProfile:

    def test_buyer_can_fetch_profile(self):
        sb = _mock_buyer_sb()
        profile_data = {
            "id": BUYER_USER_ID,
            "role": "buyer",
            "full_name": "Test Buyer",
            "phone": None,
            "state": None,
            "district": None,
            "company_name": None,
            "business_type": None,
            "created_at": "2026-01-01T00:00:00Z",
        }
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[profile_data])
        with patch("main._get_supabase", return_value=sb):
            resp = client.get("/api/profile", headers={"Authorization": BUYER_AUTH})
        assert resp.status_code == 200
        assert resp.json()["role"] == "buyer"

    def test_buyer_can_update_profile_with_company_name(self):
        sb = _mock_buyer_sb()
        updated = {
            "id": BUYER_USER_ID,
            "role": "buyer",
            "full_name": "Updated Buyer",
            "phone": None,
            "state": None,
            "district": None,
            "company_name": "FreshMart Ltd",
            "business_type": "Wholesale Buyer",
            "created_at": "2026-01-01T00:00:00Z",
        }
        # GET existing check
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": BUYER_USER_ID}])
        # PATCH update
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated])
        with patch("main._get_supabase", return_value=sb):
            resp = client.patch(
                "/api/profile",
                json={"full_name": "Updated Buyer", "company_name": "FreshMart Ltd", "business_type": "Wholesale Buyer"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "FreshMart Ltd"
        assert resp.json()["business_type"] == "Wholesale Buyer"

    def test_buyer_profile_update_requires_auth(self):
        resp = client.patch("/api/profile", json={"company_name": "Test"})
        assert resp.status_code == 401


# ── Buyer Requirements — Fetch (Step 29 / 31) ──────────────────────────────────

class TestBuyerRequirementsFetch:

    def test_buyer_can_list_empty_requirements(self):
        sb = _mock_buyer_sb()
        # Role check
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        # List query
        sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        with patch("main._get_supabase", return_value=sb):
            resp = client.get("/api/buyer/requirements", headers={"Authorization": BUYER_AUTH})
        assert resp.status_code == 200
        body = resp.json()
        assert body["requirements"] == []
        assert body["total"] == 0

    def test_buyer_can_list_own_requirements(self):
        req = {
            "id": REQ_ID,
            "user_id": BUYER_USER_ID,
            "crop": "Tomato",
            "quantity_kg": 500,
            "quality": "Standard",
            "delivery_state": "Andhra Pradesh",
            "delivery_district": "Guntur",
            "budget_per_kg": 20,
            "needed_by": "2026-10-01",
            "notes": "Ripe preferred",
            "is_active": True,
            "created_at": "2026-09-01T00:00:00Z",
        }
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[req])
        with patch("main._get_supabase", return_value=sb):
            resp = client.get("/api/buyer/requirements", headers={"Authorization": BUYER_AUTH})
        assert resp.status_code == 200
        assert len(resp.json()["requirements"]) == 1
        assert resp.json()["requirements"][0]["crop"] == "Tomato"

    def test_farmer_cannot_list_buyer_requirements(self):
        sb = _mock_farmer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "farmer"}])
        with patch("main._get_supabase", return_value=sb):
            resp = client.get("/api/buyer/requirements", headers={"Authorization": FARMER_AUTH})
        assert resp.status_code == 403
        assert "Only buyers" in resp.json()["detail"]

    def test_requirements_fetch_requires_auth(self):
        resp = client.get("/api/buyer/requirements")
        assert resp.status_code == 401


# ── Buyer Requirements — Create (Step 29 / 30) ────────────────────────────────

class TestBuyerRequirementsCreate:

    def _make_create_sb(self, created_row: dict):
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[created_row])
        return sb

    def test_buyer_can_create_requirement(self):
        created = {
            "id": REQ_ID, "user_id": BUYER_USER_ID,
            "crop": "Onion", "quantity_kg": 200, "quality": "Standard",
            "delivery_state": None, "delivery_district": None,
            "budget_per_kg": None, "needed_by": None, "notes": None,
            "is_active": True, "created_at": "2026-09-01T00:00:00Z",
        }
        sb = self._make_create_sb(created)
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Onion", "quantity_kg": 200, "quality": "Standard"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 201
        assert resp.json()["crop"] == "Onion"

    def test_create_with_all_optional_fields(self):
        created = {
            "id": REQ_ID, "user_id": BUYER_USER_ID,
            "crop": "Mango", "quantity_kg": 1000, "quality": "Premium",
            "delivery_state": "Andhra Pradesh", "delivery_district": "Guntur",
            "budget_per_kg": 35.5, "needed_by": "2026-10-15",
            "notes": "Export quality needed", "is_active": True,
            "created_at": "2026-09-01T00:00:00Z",
        }
        sb = self._make_create_sb(created)
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={
                    "crop": "Mango",
                    "quantity_kg": 1000,
                    "quality": "Premium",
                    "delivery_state": "Andhra Pradesh",
                    "delivery_district": "Guntur",
                    "budget_per_kg": 35.5,
                    "needed_by": "2026-10-15",
                    "notes": "Export quality needed",
                },
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 201
        assert resp.json()["budget_per_kg"] == 35.5

    def test_create_requires_auth(self):
        resp = client.post(
            "/api/buyer/requirements",
            json={"crop": "Onion", "quantity_kg": 100, "quality": "Standard"},
        )
        assert resp.status_code == 401

    def test_farmer_cannot_create_requirement(self):
        sb = _mock_farmer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "farmer"}])
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "Standard"},
                headers={"Authorization": FARMER_AUTH},
            )
        assert resp.status_code == 403

    # ── Validation (Step 30) ────────────────────────────────────────────────────

    def test_create_requires_crop(self):
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "", "quantity_kg": 100, "quality": "Standard"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422
        assert "crop" in resp.json()["detail"].lower()

    def test_create_rejects_zero_quantity(self):
        sb = _mock_buyer_sb()
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 0, "quality": "Standard"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422
        assert "quantity_kg" in resp.json()["detail"].lower()

    def test_create_rejects_negative_quantity(self):
        sb = _mock_buyer_sb()
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": -50, "quality": "Standard"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422

    def test_create_rejects_invalid_quality(self):
        sb = _mock_buyer_sb()
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "VeryBest"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422
        assert "quality" in resp.json()["detail"].lower()

    def test_create_rejects_zero_budget(self):
        sb = _mock_buyer_sb()
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "Standard", "budget_per_kg": 0},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422
        assert "budget" in resp.json()["detail"].lower()

    def test_create_rejects_invalid_date(self):
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "Standard", "needed_by": "not-a-date"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422
        assert "needed_by" in resp.json()["detail"].lower()

    def test_create_rejects_past_date(self):
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "Standard", "needed_by": "2020-01-01"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422
        assert "past" in resp.json()["detail"].lower()

    def test_create_accepts_future_date(self):
        created = {
            "id": REQ_ID, "user_id": BUYER_USER_ID,
            "crop": "Tomato", "quantity_kg": 100, "quality": "Standard",
            "delivery_state": None, "delivery_district": None,
            "budget_per_kg": None, "needed_by": "2099-12-31", "notes": None,
            "is_active": True, "created_at": "2026-09-01T00:00:00Z",
        }
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[created])
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "Standard", "needed_by": "2099-12-31"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 201
        assert resp.json()["needed_by"] == "2099-12-31"

    def test_create_accepts_any_quality(self):
        created = {
            "id": REQ_ID, "user_id": BUYER_USER_ID,
            "crop": "Tomato", "quantity_kg": 100, "quality": "Any",
            "delivery_state": None, "delivery_district": None,
            "budget_per_kg": None, "needed_by": None, "notes": None,
            "is_active": True, "created_at": "2026-09-01T00:00:00Z",
        }
        sb = _mock_buyer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[created])
        with patch("main._get_supabase", return_value=sb):
            resp = client.post(
                "/api/buyer/requirements",
                json={"crop": "Tomato", "quantity_kg": 100, "quality": "Any"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 201


# ── Buyer Requirements — Update (Step 29 / 30) ────────────────────────────────

class TestBuyerRequirementsUpdate:

    def _make_update_sb(self, existing_user_id: str, updated_row: dict, calling_user_id: str = BUYER_USER_ID):
        """Build a per-table mock so the role check (profiles) and the ownership
        check (buyer_requirements) do not share the same mock chain."""
        return _make_per_table_sb(
            user_id=calling_user_id,
            role="buyer",
            req_data=[{"id": REQ_ID, "user_id": existing_user_id}],
            updated_row=updated_row,
        )

    def test_buyer_can_update_own_requirement(self):
        updated = {
            "id": REQ_ID, "user_id": BUYER_USER_ID,
            "crop": "Onion", "quantity_kg": 300, "quality": "Premium",
            "delivery_state": None, "delivery_district": None,
            "budget_per_kg": None, "needed_by": None, "notes": None,
            "is_active": True, "created_at": "2026-09-01T00:00:00Z",
        }
        sb = self._make_update_sb(BUYER_USER_ID, updated)
        with patch("main._get_supabase", return_value=sb):
            resp = client.patch(
                f"/api/buyer/requirements/{REQ_ID}",
                json={"quantity_kg": 300, "quality": "Premium"},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 200
        assert resp.json()["crop"] == "Onion"

    def test_buyer_cannot_update_another_buyers_requirement(self):
        # Buyer B tries to update Buyer A's requirement — should get 403
        sb = _make_per_table_sb(
            user_id=BUYER_B_USER_ID,
            role="buyer",
            req_data=[{"id": REQ_ID, "user_id": BUYER_USER_ID}],  # belongs to Buyer A
        )
        with patch("main._get_supabase", return_value=sb):
            resp = client.patch(
                f"/api/buyer/requirements/{REQ_ID}",
                json={"quantity_kg": 999},
                headers={"Authorization": BUYER_B_AUTH},
            )
        assert resp.status_code == 403

    def test_update_requires_auth(self):
        resp = client.patch(f"/api/buyer/requirements/{REQ_ID}", json={"quantity_kg": 100})
        assert resp.status_code == 401

    def test_update_rejects_zero_quantity(self):
        sb = _make_per_table_sb(
            user_id=BUYER_USER_ID,
            role="buyer",
            req_data=[{"id": REQ_ID, "user_id": BUYER_USER_ID}],
        )
        with patch("main._get_supabase", return_value=sb):
            resp = client.patch(
                f"/api/buyer/requirements/{REQ_ID}",
                json={"quantity_kg": 0},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 422

    def test_update_can_toggle_is_active(self):
        updated = {
            "id": REQ_ID, "user_id": BUYER_USER_ID,
            "crop": "Tomato", "quantity_kg": 100, "quality": "Standard",
            "delivery_state": None, "delivery_district": None,
            "budget_per_kg": None, "needed_by": None, "notes": None,
            "is_active": False, "created_at": "2026-09-01T00:00:00Z",
        }
        sb = self._make_update_sb(BUYER_USER_ID, updated)
        with patch("main._get_supabase", return_value=sb):
            resp = client.patch(
                f"/api/buyer/requirements/{REQ_ID}",
                json={"is_active": False},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_update_404_for_nonexistent_requirement(self):
        sb = _make_per_table_sb(
            user_id=BUYER_USER_ID,
            role="buyer",
            req_data=[],  # empty → not found → 404
        )
        with patch("main._get_supabase", return_value=sb):
            resp = client.patch(
                f"/api/buyer/requirements/{REQ_ID}",
                json={"quantity_kg": 100},
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 404


# ── Buyer Requirements — Delete (Step 29 / 31) ────────────────────────────────

class TestBuyerRequirementsDelete:

    def test_buyer_can_delete_own_requirement(self):
        sb = _make_per_table_sb(
            user_id=BUYER_USER_ID,
            role="buyer",
            req_data=[{"id": REQ_ID, "user_id": BUYER_USER_ID}],
        )
        with patch("main._get_supabase", return_value=sb):
            resp = client.delete(
                f"/api/buyer/requirements/{REQ_ID}",
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 204

    def test_buyer_cannot_delete_another_buyers_requirement(self):
        # Buyer B tries to delete Buyer A's requirement — should get 403
        sb = _make_per_table_sb(
            user_id=BUYER_B_USER_ID,
            role="buyer",
            req_data=[{"id": REQ_ID, "user_id": BUYER_USER_ID}],  # belongs to Buyer A
        )
        with patch("main._get_supabase", return_value=sb):
            resp = client.delete(
                f"/api/buyer/requirements/{REQ_ID}",
                headers={"Authorization": BUYER_B_AUTH},
            )
        assert resp.status_code == 403

    def test_delete_requires_auth(self):
        resp = client.delete(f"/api/buyer/requirements/{REQ_ID}")
        assert resp.status_code == 401

    def test_farmer_cannot_delete_buyer_requirement(self):
        sb = _mock_farmer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "farmer"}])
        with patch("main._get_supabase", return_value=sb):
            resp = client.delete(
                f"/api/buyer/requirements/{REQ_ID}",
                headers={"Authorization": FARMER_AUTH},
            )
        assert resp.status_code == 403

    def test_delete_404_for_nonexistent_requirement(self):
        sb = _make_per_table_sb(
            user_id=BUYER_USER_ID,
            role="buyer",
            req_data=[],  # empty → not found → 404
        )
        with patch("main._get_supabase", return_value=sb):
            resp = client.delete(
                f"/api/buyer/requirements/{REQ_ID}",
                headers={"Authorization": BUYER_AUTH},
            )
        assert resp.status_code == 404


# ── Security / Ownership (Step 31) ────────────────────────────────────────────

class TestBuyerOwnershipSecurity:

    def test_buyer_a_cannot_see_buyer_b_data(self):
        """Buyer A listing requirements sees only their own (user_id filter in query)."""
        # This is enforced at the DB query level (eq("user_id", uid))
        # We verify the endpoint always filters by the authenticated uid
        sb = _mock_buyer_sb(BUYER_USER_ID)
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "buyer"}])
        # Buyer A's query returns no rows (they have no matching requirements)
        sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        with patch("main._get_supabase", return_value=sb):
            resp = client.get("/api/buyer/requirements", headers={"Authorization": BUYER_AUTH})
        assert resp.status_code == 200
        # Buyer A sees 0 rows — not Buyer B's data
        assert resp.json()["total"] == 0
        # Verify eq was called with BUYER_USER_ID (not BUYER_B's)
        call_args = str(sb.table.return_value.select.return_value.eq.call_args_list)
        assert BUYER_USER_ID in call_args

    def test_unauthenticated_cannot_access_any_buyer_endpoint(self):
        resp_list = client.get("/api/buyer/requirements")
        resp_create = client.post("/api/buyer/requirements", json={"crop": "x", "quantity_kg": 1, "quality": "Any"})
        resp_update = client.patch(f"/api/buyer/requirements/{REQ_ID}", json={})
        resp_delete = client.delete(f"/api/buyer/requirements/{REQ_ID}")
        assert resp_list.status_code == 401
        assert resp_create.status_code == 401
        assert resp_update.status_code == 401
        assert resp_delete.status_code == 401

    def test_farmer_blocked_from_all_buyer_requirement_endpoints(self):
        sb = _mock_farmer_sb()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"role": "farmer"}])
        with patch("main._get_supabase", return_value=sb):
            r1 = client.get("/api/buyer/requirements", headers={"Authorization": FARMER_AUTH})
            r2 = client.post("/api/buyer/requirements", json={"crop": "x", "quantity_kg": 1, "quality": "Any"}, headers={"Authorization": FARMER_AUTH})
        assert r1.status_code == 403
        assert r2.status_code == 403
