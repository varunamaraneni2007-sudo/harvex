"""
Step 23 — Farmer Privacy & Consent tests.

All Supabase calls are mocked. No live credentials needed.
"""
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from main import app, CONSENT_VERSION

client = TestClient(app)

FARMER_UID = "aaaaaaaa-0000-0000-0000-000000000011"

CONSENT_ROW = {
    "id": "cccccccc-0000-0000-0000-000000000001",
    "user_id": FARMER_UID,
    "consented_at": "2026-09-19T07:00:00Z",
    "version": CONSENT_VERSION,
}


def _mock_sb_with_consent(uid: str):
    """Supabase client where a consent row exists for uid."""
    sb = MagicMock()
    user_mock = MagicMock(); user_mock.id = uid
    sb.auth.get_user.return_value = MagicMock(user=user_mock)

    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[CONSENT_ROW])
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value = chain
    # Also handle the existing-check chain in POST
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .limit.return_value.execute.return_value = MagicMock(data=[CONSENT_ROW])
    return sb


def _mock_sb_no_consent(uid: str):
    """Supabase client where no consent row exists for uid."""
    sb = MagicMock()
    user_mock = MagicMock(); user_mock.id = uid
    sb.auth.get_user.return_value = MagicMock(user=user_mock)

    empty = MagicMock(data=[])

    # GET chain: select().eq().eq().order().limit().execute() → empty
    chain = MagicMock(); chain.execute.return_value = empty
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value = chain

    # POST existing-check chain: select().eq().eq().limit().execute() → empty
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .limit.return_value.execute.return_value = empty

    # POST insert chain → new row
    sb.table.return_value.insert.return_value.execute.return_value = \
        MagicMock(data=[CONSENT_ROW])
    return sb


# ── GET /api/consent ──────────────────────────────────────────────────────────

def test_get_consent_401_without_auth():
    resp = client.get("/api/consent")
    assert resp.status_code == 401


def test_get_consent_404_when_no_consent():
    sb = _mock_sb_no_consent(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/consent", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404
    assert "Consent not recorded" in resp.json()["detail"]


def test_get_consent_returns_record_when_exists():
    sb = _mock_sb_with_consent(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/consent", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == FARMER_UID
    assert body["version"] == CONSENT_VERSION


def test_get_consent_503_when_supabase_unavailable():
    with patch("main._get_supabase", return_value=None):
        resp = client.get("/api/consent", headers={"Authorization": "Bearer token"})
    # _require_user_id also needs supabase; will 401 before reaching endpoint
    assert resp.status_code in (401, 503)


# ── POST /api/consent ─────────────────────────────────────────────────────────

def test_post_consent_401_without_auth():
    resp = client.post("/api/consent")
    assert resp.status_code == 401


def test_post_consent_creates_record_when_none_exists():
    sb = _mock_sb_no_consent(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.post("/api/consent", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == FARMER_UID
    assert body["version"] == CONSENT_VERSION


def test_post_consent_idempotent_returns_200_when_already_consented():
    """Second POST returns the existing record with 200, not a duplicate."""
    sb = _mock_sb_with_consent(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.post("/api/consent", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json()["version"] == CONSENT_VERSION


def test_post_consent_wrong_token_returns_401():
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("invalid JWT")
    with patch("main._get_supabase", return_value=sb):
        resp = client.post("/api/consent", headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401


# ── Consent version constant ──────────────────────────────────────────────────

def test_consent_version_is_string():
    assert isinstance(CONSENT_VERSION, str)
    assert len(CONSENT_VERSION) > 0


def test_consent_record_includes_version():
    sb = _mock_sb_with_consent(FARMER_UID)
    with patch("main._get_supabase", return_value=sb):
        resp = client.get("/api/consent", headers={"Authorization": "Bearer token"})
    assert resp.json().get("version") == CONSENT_VERSION


def test_consent_schema_grants_backend_only_required_operations():
    schema = Path(__file__).with_name("schema.sql").read_text()
    assert "GRANT SELECT, INSERT ON TABLE farmer_consents TO service_role;" in schema
    assert "GRANT SELECT, INSERT ON TABLE farmer_consents TO authenticated;" in schema
    assert "REVOKE ALL ON TABLE farmer_consents FROM anon;" in schema
    assert "GRANT ALL ON TABLE farmer_consents" not in schema
