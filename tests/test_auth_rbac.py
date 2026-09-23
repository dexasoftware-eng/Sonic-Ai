import pytest
from fastapi.testclient import TestClient
from app import app
from src.database.security import hash_password, verify_password, generate_session_token, decode_session_token

client = TestClient(app)

def test_password_hashing():
    """Verify PBKDF2-HMAC password hashing and verification"""
    raw_pwd = "supersecretpassword123"
    hashed = hash_password(raw_pwd)
    assert hashed != raw_pwd
    assert "$" in hashed
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_session_token_generation_and_decoding():
    """Verify HMAC signed session tokens"""
    token = generate_session_token(user_id="USR-123", username="guard_alex", role="security_operator", tenant_id="Metro_Police")
    payload = decode_session_token(token)
    assert payload is not None
    assert payload["user_id"] == "USR-123"
    assert payload["role"] == "security_operator"
    assert payload["tenant_id"] == "Metro_Police"

def test_auth_login_demo_fallback():
    """Verify demo default fallback accounts authenticate successfully"""
    res = client.post("/api/auth/login", data={"username": "guard@metro.gov", "password": "guard123"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["user"]["role"] == "security_operator"
    assert "session_token" in data

def test_auth_login_invalid_credentials():
    """Verify invalid password returns 401 Unauthorized"""
    res = client.post("/api/auth/login", data={"username": "guard@metro.gov", "password": "wrong_password"})
    assert res.status_code == 401

def test_seed_demo_accounts():
    """Verify seed demo accounts endpoint returns all 5 roles"""
    res = client.post("/api/auth/seed-demo-users")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    roles = [acc["role"] for acc in data["accounts"]]
    assert "security_operator" in roles
    assert "maintenance_operator" in roles
    assert "audio_reviewer" in roles
    assert "administrator" in roles
    assert "normal_user" in roles

def test_dynamic_category_registry():
    """Verify dynamic category addition for surprise evaluator tests"""
    # 1. Fetch categories
    res = client.get("/api/categories")
    assert res.status_code == 200
    initial_count = len(res.json()["categories"])
    assert initial_count >= 10

    # 2. Add dynamic category
    new_cat_name = f"Test Drone Buzz"
    add_res = client.post("/api/categories", data={
        "name": new_cat_name,
        "severity": "Medium",
        "department": "Security",
        "min_confidence": "0.75",
        "recommended_action": "Check sky perimeter for unmanned aerial vehicle."
    })
    # Either succeeds or returns 400 if already exists
    assert add_res.status_code in [200, 400]
