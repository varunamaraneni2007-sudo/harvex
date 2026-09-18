"""
Persistence layer tests.

Supabase calls are mocked — no live credentials needed.
All tests patch `main._get_supabase` so the global singleton is untouched.
"""
from unittest.mock import MagicMock, patch, call
import os
import pytest

from main import (
    ProduceInput,
    _get_supabase,
    _save_to_supabase,
    submission,
    optimize,
    plans,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _input(**overrides):
    base = dict(
        crop="onion",
        quantity_kg=400,
        quality="Standard",
        farmer_location="Vijayawada",
        harvest_date="18/09/2026",
        shelf_life_days=5,
    )
    base.update(overrides)
    return ProduceInput(**base)


def _mock_supabase():
    """Build a mock Supabase client whose table().insert().execute() always
    succeeds and returns a row with a predictable id."""
    uid_counter = [0]

    def fake_execute(self_=None):
        uid_counter[0] += 1
        return MagicMock(data=[{"id": f"fake-uuid-{uid_counter[0]:04d}"}])

    insert_mock = MagicMock()
    insert_mock.execute.side_effect = fake_execute

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock

    sb = MagicMock()
    sb.table.return_value = table_mock
    return sb


# ── _get_supabase ─────────────────────────────────────────────────────────────

def test_get_supabase_returns_none_without_credentials():
    import main
    original = main._supabase_client
    main._supabase_client = None
    try:
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            result = _get_supabase()
            assert result is None
    finally:
        main._supabase_client = original


# ── _save_to_supabase ─────────────────────────────────────────────────────────

def test_save_returns_none_when_supabase_unavailable():
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    with patch("main._get_supabase", return_value=None):
        result = _save_to_supabase(data, opt, pl)
    assert result is None


def test_save_returns_farmer_input_id_on_success():
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    sb = _mock_supabase()
    with patch("main._get_supabase", return_value=sb):
        result = _save_to_supabase(data, opt, pl)
    # First insert is farmer_inputs → id = fake-uuid-0001
    assert result == "fake-uuid-0001"


def test_save_inserts_farmer_input_row():
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    sb = _mock_supabase()
    with patch("main._get_supabase", return_value=sb):
        _save_to_supabase(data, opt, pl)
    sb.table.assert_any_call("farmer_inputs")


def test_save_inserts_decision_results():
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    sb = _mock_supabase()
    with patch("main._get_supabase", return_value=sb):
        _save_to_supabase(data, opt, pl)
    sb.table.assert_any_call("decision_results")


def test_save_inserts_allocations():
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    sb = _mock_supabase()
    with patch("main._get_supabase", return_value=sb):
        _save_to_supabase(data, opt, pl)
    sb.table.assert_any_call("allocations")


def test_save_inserts_four_plan_results():
    """One decision_result row per plan: optimize_recommended, plan_a, plan_b, plan_c."""
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    sb = _mock_supabase()
    with patch("main._get_supabase", return_value=sb):
        _save_to_supabase(data, opt, pl)

    inserted_plan_names = [
        kw.get("plan_name")
        for c in sb.table.return_value.insert.call_args_list
        for kw in [c.args[0] if c.args else {}]
        if "plan_name" in kw
    ]
    assert set(inserted_plan_names) == {
        "optimize_recommended", "plan_a", "plan_b", "plan_c"
    }


def test_save_returns_none_on_supabase_exception():
    """Any exception inside the save must be swallowed — never propagate."""
    data = _input()
    opt = optimize(data)
    pl = plans(data)
    sb = MagicMock()
    sb.table.side_effect = RuntimeError("network timeout")
    with patch("main._get_supabase", return_value=sb):
        result = _save_to_supabase(data, opt, pl)
    assert result is None


# ── /api/submission endpoint ──────────────────────────────────────────────────

def test_submission_returns_results_without_supabase():
    """Endpoint must return correct results even when Supabase is unavailable."""
    with patch("main._get_supabase", return_value=None):
        resp = submission(_input())
    assert resp.optimize is not None
    assert resp.plans is not None
    assert resp.saved is False
    assert resp.farmer_input_id is None


def test_submission_returns_saved_true_when_supabase_available():
    sb = _mock_supabase()
    with patch("main._get_supabase", return_value=sb):
        resp = submission(_input())
    assert resp.saved is True
    assert resp.farmer_input_id is not None


def test_submission_optimize_results_correct():
    """Existing decision calculations are unaffected by persistence layer."""
    with patch("main._get_supabase", return_value=None):
        resp = submission(_input())
    assert resp.optimize.recommended.total_net_value > 0
    assert resp.optimize.recommended.total_quantity_allocated <= 400.01


def test_submission_plan_a_correct():
    with patch("main._get_supabase", return_value=None):
        resp = submission(_input())
    assert resp.plans.plan_a.total_net_value == 6542.0
    alloc = {c.market_name: c.quantity_kg for c in resp.plans.plan_a.allocations}
    assert alloc.get("FreshLink Retail Aggregator") == 300.0
    assert alloc.get("Hyderabad Metro Market") == 100.0


def test_submission_all_plans_present():
    with patch("main._get_supabase", return_value=None):
        resp = submission(_input())
    assert resp.plans.plan_a.plan_label == "A"
    assert resp.plans.plan_b.plan_label == "B"
    assert resp.plans.plan_c.plan_label == "C"
