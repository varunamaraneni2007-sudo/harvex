"""
Tests for Google Places API (New) proxy — autocomplete_places, get_place_details,
and the /api/places/autocomplete and /api/places/details endpoints.

All HTTP calls are mocked — no live API key required.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
import maps_service


# ── Helpers ───────────────────────────────────────────────────────────────────

def _autocomplete_response(suggestions: list):
    """Build a mock httpx POST response for Places Autocomplete (New)."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {"suggestions": suggestions}
    return m


def _place_pred(place_id: str, text: str, main: str, secondary: str) -> dict:
    return {
        "placePrediction": {
            "placeId": place_id,
            "text": {"text": text},
            "structuredFormat": {
                "mainText": {"text": main},
                "secondaryText": {"text": secondary},
            },
        }
    }


def _details_response(place_id: str, name: str, address: str, lat: float, lng: float):
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "id": place_id,
        "displayName": {"text": name},
        "formattedAddress": address,
        "location": {"latitude": lat, "longitude": lng},
    }
    return m


# ── autocomplete_places — no API key ─────────────────────────────────────────

def test_autocomplete_returns_empty_without_api_key():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}):
        result = maps_service.autocomplete_places("Vijayawada")
    assert result == []


def test_autocomplete_returns_empty_for_blank_input():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        result = maps_service.autocomplete_places("   ")
    assert result == []


# ── autocomplete_places — successful response ─────────────────────────────────

def test_autocomplete_parses_suggestions():
    raw = [
        _place_pred("place1", "Vijayawada, Andhra Pradesh, India", "Vijayawada", "Andhra Pradesh, India"),
        _place_pred("place2", "Vijayawada Rural", "Vijayawada Rural", "Andhra Pradesh, India"),
    ]
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.post", return_value=_autocomplete_response(raw)):
            result = maps_service.autocomplete_places("Vijayawada")

    assert len(result) == 2
    assert result[0]["place_id"] == "place1"
    assert result[0]["main_text"] == "Vijayawada"
    assert result[0]["secondary_text"] == "Andhra Pradesh, India"
    assert result[1]["place_id"] == "place2"


def test_autocomplete_returns_empty_on_network_error():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.post", side_effect=Exception("network error")):
            result = maps_service.autocomplete_places("Vijayawada")
    assert result == []


def test_autocomplete_skips_entries_without_place_prediction():
    raw = [{"queryPrediction": {"text": {"text": "something"}}}]  # no placePrediction
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.post", return_value=_autocomplete_response(raw)):
            result = maps_service.autocomplete_places("something")
    assert result == []


def test_autocomplete_region_bias_is_india():
    """Verify the request body includes regionCode: IN."""
    captured = {}

    def _capture_post(url, *, headers, json, timeout):
        captured["body"] = json
        return _autocomplete_response([])

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.post", side_effect=_capture_post):
            maps_service.autocomplete_places("Guntur")

    assert captured["body"].get("regionCode") == "IN"


def test_autocomplete_includes_session_token_when_provided():
    captured = {}

    def _capture_post(url, *, headers, json, timeout):
        captured["body"] = json
        return _autocomplete_response([])

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.post", side_effect=_capture_post):
            maps_service.autocomplete_places("Guntur", session_token="tok-abc-123")

    assert captured["body"].get("sessionToken") == "tok-abc-123"


# ── get_place_details ─────────────────────────────────────────────────────────

def test_get_place_details_returns_none_without_api_key():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}):
        result = maps_service.get_place_details("ChIJ_place123")
    assert result is None


def test_get_place_details_returns_none_for_empty_id():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        result = maps_service.get_place_details("   ")
    assert result is None


def test_get_place_details_returns_correct_fields():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch(
            "httpx.get",
            return_value=_details_response(
                "ChIJplace1",
                "Vijayawada",
                "Vijayawada, Andhra Pradesh 520001, India",
                16.5062,
                80.6480,
            ),
        ):
            result = maps_service.get_place_details("ChIJplace1")

    assert result is not None
    assert result["place_id"] == "ChIJplace1"
    assert result["name"] == "Vijayawada"
    assert result["formatted_address"] == "Vijayawada, Andhra Pradesh 520001, India"
    assert abs(result["lat"] - 16.5062) < 0.0001
    assert abs(result["lng"] - 80.6480) < 0.0001


def test_get_place_details_returns_none_on_network_error():
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", side_effect=Exception("timeout")):
            result = maps_service.get_place_details("ChIJplace1")
    assert result is None


def test_get_place_details_lat_lng_can_be_none_when_missing():
    """If location field is absent from the response, lat/lng are None."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "id": "ChIJplace2",
        "displayName": {"text": "Some Place"},
        "formattedAddress": "Somewhere, India",
        # no "location" key
    }
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", return_value=m):
            result = maps_service.get_place_details("ChIJplace2")

    assert result is not None
    assert result["lat"] is None
    assert result["lng"] is None


# ── /api/places/autocomplete endpoint ────────────────────────────────────────

def test_endpoint_autocomplete_returns_suggestions_and_flag():
    from fastapi.testclient import TestClient
    from main import app

    raw = [_place_pred("pid1", "Guntur, AP, India", "Guntur", "Andhra Pradesh, India")]
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.post", return_value=_autocomplete_response(raw)):
            client = TestClient(app)
            resp = client.get("/api/places/autocomplete?input=Guntur")

    assert resp.status_code == 200
    data = resp.json()
    assert data["maps_configured"] is True
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["place_id"] == "pid1"


def test_endpoint_autocomplete_maps_configured_false_without_key():
    from fastapi.testclient import TestClient
    from main import app

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}):
        client = TestClient(app)
        resp = client.get("/api/places/autocomplete?input=Vijayawada")

    assert resp.status_code == 200
    data = resp.json()
    assert data["maps_configured"] is False
    assert data["suggestions"] == []


def test_endpoint_autocomplete_requires_input_param():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    resp = client.get("/api/places/autocomplete")
    assert resp.status_code == 422  # FastAPI validation: missing required query param


# ── /api/places/details endpoint ─────────────────────────────────────────────

def test_endpoint_details_returns_place_data():
    from fastapi.testclient import TestClient
    from main import app

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch(
            "httpx.get",
            return_value=_details_response(
                "ChIJpid1",
                "Hyderabad",
                "Hyderabad, Telangana, India",
                17.3850,
                78.4867,
            ),
        ):
            client = TestClient(app)
            resp = client.get("/api/places/details?place_id=ChIJpid1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["maps_configured"] is True
    assert data["place"]["formatted_address"] == "Hyderabad, Telangana, India"
    assert abs(data["place"]["lat"] - 17.3850) < 0.0001
    assert abs(data["place"]["lng"] - 78.4867) < 0.0001


def test_endpoint_details_returns_null_place_without_key():
    from fastapi.testclient import TestClient
    from main import app

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}):
        client = TestClient(app)
        resp = client.get("/api/places/details?place_id=ChIJpid1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["maps_configured"] is False
    assert data["place"] is None


def test_endpoint_details_requires_place_id_param():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    resp = client.get("/api/places/details")
    assert resp.status_code == 422
