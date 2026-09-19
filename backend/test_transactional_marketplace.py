"""Focused authorization and validation tests for the transactional marketplace."""
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
FARMER = "aaaaaaaa-0000-0000-0000-000000000001"
BUYER = "bbbbbbbb-0000-0000-0000-000000000002"


def supabase_for(uid: str, role: str):
    sb = MagicMock()
    user = MagicMock(id=uid); auth = MagicMock(user=user); sb.auth.get_user.return_value = auth
    profile = {"id": uid, "role": role, "public_id": "F001" if role == "farmer" else "B001",
               "average_rating": 0, "total_ratings": 0}
    profile_eq = MagicMock(); profile_eq.execute.return_value = MagicMock(data=[profile])
    profile_select = MagicMock(); profile_select.eq.return_value = profile_eq
    profile_table = MagicMock(); profile_table.select.return_value = profile_select
    sb.table.side_effect = lambda name: profile_table if name == "profiles" else MagicMock()
    return sb


def headers():
    return {"Authorization": "Bearer token"}


def test_anonymous_cannot_view_transactional_listings():
    assert client.get("/api/crop-listings").status_code == 401


def test_buyer_cannot_create_farmer_listing():
    sb = supabase_for(BUYER, "buyer")
    with patch("main._get_supabase", return_value=sb):
        response = client.post("/api/farmer/listings", headers=headers(), json={
            "crop_name":"Tomato","available_quantity_kg":50,"price_per_kg":25,
            "quality":"Premium","harvest_date":"2026-09-19","location":"Guntur",
            "status":"available","photo_paths":[f"{BUYER}/listing/photo.jpg"]})
    assert response.status_code == 403


def test_published_listing_requires_actual_photo():
    sb = supabase_for(FARMER, "farmer")
    with patch("main._get_supabase", return_value=sb):
        response = client.post("/api/farmer/listings", headers=headers(), json={
            "crop_name":"Tomato","available_quantity_kg":50,"price_per_kg":25,
            "quality":"Premium","harvest_date":"2026-09-19","location":"Guntur",
            "status":"available","photo_paths":[]})
    assert response.status_code == 422
    assert "photo" in response.json()["detail"].lower()


def test_farmer_cannot_attach_another_users_photo():
    sb = supabase_for(FARMER, "farmer")
    with patch("main._get_supabase", return_value=sb):
        response = client.post("/api/farmer/listings", headers=headers(), json={
            "crop_name":"Tomato","available_quantity_kg":50,"price_per_kg":25,
            "quality":"Premium","harvest_date":"2026-09-19","location":"Guntur",
            "status":"available","photo_paths":["another-user/listing/photo.jpg"]})
    assert response.status_code == 403


def test_farmer_cannot_place_order():
    sb = supabase_for(FARMER, "farmer")
    with patch("main._get_supabase", return_value=sb):
        response = client.post("/api/marketplace/orders", headers=headers(), json={
            "crop_name":"Tomato","quantity_kg":10})
    assert response.status_code == 403


def test_buyer_order_uses_atomic_database_function():
    sb = supabase_for(BUYER, "buyer")
    rpc = MagicMock(); rpc.execute.return_value = MagicMock(data="order-001"); sb.rpc.return_value = rpc
    with patch("main._get_supabase", return_value=sb):
        response = client.post("/api/marketplace/orders", headers=headers(), json={
            "crop_name":"Tomato","quantity_kg":600,"quality":"Premium"})
    assert response.status_code == 201
    assert response.json()["order_id"] == "order-001"
    sb.rpc.assert_called_once_with("place_marketplace_order", {
        "p_purchaser":BUYER,"p_crop":"Tomato","p_quantity":600.0,"p_quality":"Premium"})


def test_rating_value_is_limited_to_five():
    sb = supabase_for(BUYER, "buyer")
    with patch("main._get_supabase", return_value=sb):
        response = client.post("/api/marketplace/ratings", headers=headers(), json={
            "order_item_id":"item-1","rating":6,"review_text":"invalid"})
    assert response.status_code == 422
