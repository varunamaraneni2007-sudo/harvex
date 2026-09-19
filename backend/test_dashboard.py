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
