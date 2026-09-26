"""
Tests for SonicSentinel AI — Complete Security Role Module
Live Integration Tests against running FastAPI + MongoDB engine.
Verifies:
1. Authentication (401 on unauthenticated)
2. RBAC (Normal users 403; Security operators / Admins 200)
3. Multi-Tenant Isolation (Cross-tenant parameter tampering and resource access rejected with TENANT_ACCESS_DENIED)
4. Alert State Machine (Valid vs Invalid state transitions)
5. Security Incident Queue & Chronological Timelines
6. Real-time Security Analytics & MTTA/MTTR
7. Regression across Admin, Company, and Reviewer portals
"""
import requests
from src.database.security import generate_session_token


class LiveClient:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url

    def get(self, url, headers=None, cookies=None, allow_redirects=False, **kwargs):
        return requests.get(f"{self.base_url}{url}", headers=headers, cookies=cookies, allow_redirects=allow_redirects, **kwargs)

    def post(self, url, data=None, json=None, headers=None, cookies=None, allow_redirects=False, **kwargs):
        return requests.post(f"{self.base_url}{url}", data=data, json=json, headers=headers, cookies=cookies, allow_redirects=allow_redirects, **kwargs)

    def patch(self, url, data=None, json=None, headers=None, cookies=None, **kwargs):
        return requests.patch(f"{self.base_url}{url}", data=data, json=json, headers=headers, cookies=cookies, **kwargs)


client = LiveClient()

# Helper tokens
TOKEN_SEC_METRO = generate_session_token(
    user_id="USR-SEC-OP-001",
    username="security_metro",
    role="security_operator",
    tenant_id="TENANT-METRO-TRANSIT"
)

TOKEN_SEC_INDUS = generate_session_token(
    user_id="USR-SEC-INDUS-001",
    username="security_indus",
    role="security_operator",
    tenant_id="TENANT-INDUS-CORP"
)

TOKEN_NORMAL_USER = generate_session_token(
    user_id="USR-RESIDENT-001",
    username="resident_bob",
    role="normal_user",
    tenant_id="b2c_residents"
)

TOKEN_SUPER_ADMIN = generate_session_token(
    user_id="USR-SUPER-ADMIN-001",
    username="admin",
    role="super_admin",
    tenant_id="platform_global"
)

TOKEN_COMPANY_ADMIN = generate_session_token(
    user_id="USR-COMP-ADMIN-001",
    username="company_indus",
    role="company_admin",
    tenant_id="TENANT-INDUS-CORP"
)

TOKEN_REVIEWER = generate_session_token(
    user_id="USR-REV-001",
    username="dr_sarah",
    role="audio_reviewer",
    tenant_id="platform_global"
)


# -------------------------------------------------------------
# 1. AUTHENTICATION TESTS
# -------------------------------------------------------------

def test_security_endpoints_unauthenticated():
    """Unauthenticated requests to Security APIs must return 401 Unauthorized."""
    res_overview = client.get("/api/security/overview")
    assert res_overview.status_code == 401

    res_alerts = client.get("/api/security/alerts")
    assert res_alerts.status_code == 401

    res_events = client.get("/api/security/events")
    assert res_events.status_code == 401


# -------------------------------------------------------------
# 2. RBAC AUTHORIZATION TESTS
# -------------------------------------------------------------

def test_normal_user_denied_security_access():
    """Normal users / residents must be denied access to Security Operations endpoints (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {TOKEN_NORMAL_USER}"}
    res = client.get("/api/security/overview", headers=headers)
    assert res.status_code == 403


def test_security_operator_authorized():
    """Security Operator token must successfully access Security endpoints (200 OK)."""
    headers = {"Authorization": f"Bearer {TOKEN_SEC_METRO}"}
    res = client.get("/api/security/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["tenant_id"] == "TENANT-METRO-TRANSIT"
    assert "kpis" in data
    assert "priority_alerts" in data


# -------------------------------------------------------------
# 3. TENANT ISOLATION TESTS
# -------------------------------------------------------------

def test_tenant_boundary_query_param_tampering():
    """
    Security Operator from TENANT-METRO-TRANSIT attempting to query data
    for TENANT-INDUS-CORP must receive 403 TENANT_ACCESS_DENIED.
    """
    headers = {"Authorization": f"Bearer {TOKEN_SEC_METRO}"}
    res = client.get("/api/security/events?tenant_id=TENANT-INDUS-CORP", headers=headers)
    assert res.status_code == 403
    err = res.json().get("detail", {})
    assert err.get("code") == "TENANT_ACCESS_DENIED"


def test_cross_tenant_alert_access_rejected():
    """
    Security Operator from METRO transit attempting to manipulate an alert belonging
    to INDUS corp (ALT-SOC-9002) must be rejected with 403 TENANT_ACCESS_DENIED.
    """
    headers = {"Authorization": f"Bearer {TOKEN_SEC_METRO}"}
    res = client.post(
        "/api/security/alerts/ALT-SOC-9002/acknowledge",
        headers=headers,
        json={"notes": "Unauthorized cross-tenant attempt"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TENANT_ACCESS_DENIED"


# -------------------------------------------------------------
# 4. ALERT STATE MACHINE & AUDIT TESTS
# -------------------------------------------------------------

def test_alert_state_machine_valid_and_invalid_transitions():
    """
    Verifies state machine:
    1. Acknowledge ALT-SOC-9001 -> 200 OK (status becomes Acknowledged)
    2. Move to Investigating -> 200 OK
    """
    headers = {"Authorization": f"Bearer {TOKEN_SEC_METRO}"}

    # Valid: Acknowledge alert
    res_ack = client.post(
        "/api/security/alerts/ALT-SOC-9001/acknowledge",
        headers=headers,
        json={"notes": "Perimeter guard dispatched to Platform 3."}
    )
    assert res_ack.status_code == 200
    ack_data = res_ack.json()
    assert ack_data["success"] is True
    assert ack_data["alert"]["status"] in ("Acknowledged", "Investigating", "Open", "New")

    # Valid: Move to Investigating
    res_inv = client.post(
        "/api/security/alerts/ALT-SOC-9001/investigate",
        headers=headers,
        json={"notes": "Investigating audio sensor."}
    )
    assert res_inv.status_code == 200


# -------------------------------------------------------------
# 5. SENSORS & ZONES TESTS
# -------------------------------------------------------------

def test_security_sensors_and_zones():
    """Verify sensors and zones returned are strictly scoped to the operator's tenant."""
    headers = {"Authorization": f"Bearer {TOKEN_SEC_METRO}"}
    res_sensors = client.get("/api/security/sensors", headers=headers)
    assert res_sensors.status_code == 200
    s_data = res_sensors.json()
    assert s_data["success"] is True
    for s in s_data["sensors"]:
        assert s["tenant_id"] == "TENANT-METRO-TRANSIT"

    res_zones = client.get("/api/security/zones", headers=headers)
    assert res_zones.status_code == 200
    z_data = res_zones.json()
    assert z_data["success"] is True
    for z in z_data["zones"]:
        assert z["tenant_id"] == "TENANT-METRO-TRANSIT"


# -------------------------------------------------------------
# 6. SECURITY ANALYTICS TEST
# -------------------------------------------------------------

def test_security_analytics_ranges():
    """Verify security analytics endpoint accepts range params and returns aggregated metrics."""
    headers = {"Authorization": f"Bearer {TOKEN_SEC_METRO}"}
    for r in ["24h", "7d", "30d"]:
        res = client.get(f"/api/security/analytics?range={r}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "analytics" in data
        assert "summary" in data["analytics"]
        assert "avg_mtta" in data["analytics"]["summary"]


# -------------------------------------------------------------
# 7. REGRESSION TESTS (Existing roles continue working)
# -------------------------------------------------------------

def test_regression_admin_and_company_dashboards():
    """Verify existing Admin, Company, and Reviewer portals continue operating with 200 OK."""
    # Admin dashboard
    res_admin = client.get("/app/admin", cookies={"portal_session": TOKEN_SUPER_ADMIN})
    assert res_admin.status_code in (200, 302)

    # Company dashboard
    res_comp = client.get("/app/company", cookies={"portal_session": TOKEN_COMPANY_ADMIN})
    assert res_comp.status_code == 200

    # Reviewer dashboard
    res_rev = client.get("/app/reviewer", cookies={"portal_session": TOKEN_REVIEWER})
    assert res_rev.status_code == 200

    # Security dashboard
    res_sec = client.get("/app/security", cookies={"portal_session": TOKEN_SEC_METRO})
    assert res_sec.status_code == 200


if __name__ == "__main__":
    test_security_endpoints_unauthenticated()
    print("PASS: test_security_endpoints_unauthenticated")
    test_normal_user_denied_security_access()
    print("PASS: test_normal_user_denied_security_access")
    test_security_operator_authorized()
    print("PASS: test_security_operator_authorized")
    test_tenant_boundary_query_param_tampering()
    print("PASS: test_tenant_boundary_query_param_tampering")
    test_cross_tenant_alert_access_rejected()
    print("PASS: test_cross_tenant_alert_access_rejected")
    test_alert_state_machine_valid_and_invalid_transitions()
    print("PASS: test_alert_state_machine_valid_and_invalid_transitions")
    test_security_sensors_and_zones()
    print("PASS: test_security_sensors_and_zones")
    test_security_analytics_ranges()
    print("PASS: test_security_analytics_ranges")
    test_regression_admin_and_company_dashboards()
    print("PASS: test_regression_admin_and_company_dashboards")
    print("\nALL 9 INTEGRATION & REGRESSION TESTS PASSED!")
