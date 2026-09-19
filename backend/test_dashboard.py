"""
Step 25 — Farmer Dashboard: GET /api/farmer/submissions tests.
All Supabase calls are mocked. No live credentials needed.
"""
from unittest.mock import MagicMock, patch, call
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

FARMER_UID = "aaaaaaaa-0000-0000-0000-000000000033"

SAMPLE_INPUT = {
    "id": "ffffffff-0000-0000-0000-000000000001",
    "crop": "Tomato",
    "quantity_kg": 500,
    "quality": "Premium",
    "farmer_location": "Guntur, Andhra Pradesh",
    "harvest_date": "2026-09-19",
    "shelf_life_days": 7,
    "created_at": "2026-09-19T07:00:00Z",
}

SAMPLE_RESULT = {
    "plan_name": "optimize_recommended",
    "total_allocated_kg": 500,
    "gross_revenue": 11500.0,
    "transport_cost": 500.0,
    "spoilage_loss": 690.0,
    "expected_net_value": 10310.0,
}


def _mock_sb_with_submissions(uid: str, inputs=None, result=None):
    """Supabase mock that returns submissions for the farmer."""
    sb = MagicMock()
    user_mock = MagicMock()
    user_mock.id = uid
    sb.auth.get_user.return_value = MagicMock(user=user_mock)

    inputs = inputs if inputs is not None else [SAMPLE_INPUT]
    result_data = [result] if result else [SAMPLE_RESULT]

    # profiles role check: select().eq().execute() → farmer role
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"role": "farmer"}]
    )

    # farmer_inputs chain: select().eq().order().limit().execute()
    inputs_chain = MagicMock()
    inputs_chain.execute.return_value = MagicMock(data=inputs)
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value = inputs_chain

    # decision_results chain: select().eq().eq().limit().execute()
    result_chain = MagicMock()
    result_chain.execute.return_value = MagicMock(data=result_data)
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = result_chain

    return sb


def _mock_sb_no_submissions(uid: str):
    """Supabase mock that returns no submissions."""
    sb = MagicMock()
    user_mock = MagicMock()
    user_mock.id = uid
    sb.auth.get_user.return_value = MagicMock(user=user_mock)

    # profiles role check
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"role": "farmer"}]
    )

    empty_chain = MagicMock()
    empty_chain.execute.return_value = MagicMock(data=[])
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value = empty_chain

    return sb


# ── GET /api/farmer/submissions ───────────────────────────────────────────────

def test_submissions_401_without_auth():
    resp = client.get("/api/farmer/submissions")
    assert resp.status_code == 401


def test_submissions_returns_empty_list_when_no_data():
    sb = _mock_sb_no_submissions(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["submissions"] == []
    assert body["total"] == 0


def test_submissions_returns_data_with_result():
    sb = _mock_sb_with_submissions(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    sub = body["submissions"][0]
    assert sub["farmer_input"]["crop"] == "Tomato"
    assert sub["recommended_result"]["expected_net_value"] == 10310.0


def test_submissions_farmer_input_contains_expected_fields():
    sb = _mock_sb_with_submissions(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer token"},
        )
    fi = resp.json()["submissions"][0]["farmer_input"]
    assert "crop" in fi
    assert "quantity_kg" in fi
    assert "quality" in fi
    assert "farmer_location" in fi
    assert "created_at" in fi


def test_submissions_result_can_be_null():
    """When no decision result was saved, recommended_result is null."""
    sb = _mock_sb_with_submissions(FARMER_UID, inputs=[SAMPLE_INPUT], result=None)
    # Override result chain to return empty
    result_chain = MagicMock()
    result_chain.execute.return_value = MagicMock(data=[])
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = result_chain

    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert resp.json()["submissions"][0]["recommended_result"] is None


def test_submissions_503_when_supabase_unavailable():
    with patch("main._get_supabase", return_value=None):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code in (401, 503)


def test_submissions_wrong_token_returns_401():
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("invalid JWT")
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer bad"},
        )
    assert resp.status_code == 401


def test_submissions_limit_param_is_respected():
    sb = MagicMock()
    user_mock = MagicMock()
    user_mock.id = FARMER_UID
    sb.auth.get_user.return_value = MagicMock(user=user_mock)

    # profiles role check
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"role": "farmer"}]
    )

    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value = chain

    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions?limit=3",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    # Verify .limit(3) was called somewhere in the chain
    limit_calls = sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.call_args_list
    assert any(c == call(3) for c in limit_calls)


def test_submissions_limit_out_of_range_returns_422():
    """limit must be between 1 and 20."""
    sb = MagicMock()
    sb.auth.get_user.return_value = MagicMock(user=MagicMock(id=FARMER_UID))
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions?limit=100",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ── [Step 26] Data ownership / isolation ─────────────────────────────────────

def test_submissions_filters_by_jwt_user_id():
    """The endpoint must pass the JWT user's UID — not a caller-supplied value — to the DB filter."""
    sb = _mock_sb_with_submissions(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get(
            "/api/farmer/submissions",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    # Verify that eq("user_id", FARMER_UID) was called on the farmer_inputs query
    eq_calls = sb.table.return_value.select.return_value.eq.call_args_list
    user_id_filters = [c for c in eq_calls if c.args and c.args[0] == "user_id"]
    assert any(c.args[1] == FARMER_UID for c in user_id_filters), (
        "The user_id filter must use the UID from the JWT, not an arbitrary value"
    )


def test_submissions_different_uids_see_different_data():
    """Two farmers with different UIDs get only their own submissions."""
    FARMER_A = "aaaaaaaa-0000-0000-0000-000000000033"
    FARMER_B = "bbbbbbbb-0000-0000-0000-000000000099"

    input_a = {**SAMPLE_INPUT, "id": "fa-0001", "crop": "Tomato"}
    input_b = {**SAMPLE_INPUT, "id": "fb-0001", "crop": "Onion"}

    sb_a = _mock_sb_with_submissions(FARMER_A, inputs=[input_a])
    sb_b = _mock_sb_with_submissions(FARMER_B, inputs=[input_b])

    with patch("main._get_supabase", return_value=sb_a):
        resp_a = client.get("/api/farmer/submissions", headers={"Authorization": "Bearer tokenA"})
    with patch("main._get_supabase", return_value=sb_b):
        resp_b = client.get("/api/farmer/submissions", headers={"Authorization": "Bearer tokenB"})

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["submissions"][0]["farmer_input"]["crop"] == "Tomato"
    assert resp_b.json()["submissions"][0]["farmer_input"]["crop"] == "Onion"
