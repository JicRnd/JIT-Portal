from __future__ import annotations

import pytest

from app import create_app
from app.db import get_session
from app.models_db import User


@pytest.fixture
def app():
    application = create_app()
    application.testing = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _metric_payload(series: str) -> dict:
    if series == "IMH":
        bore, rod, mount = "40", "25", "MF1"
    else:
        bore, rod, mount = "25", "12", "MX0"
    return {
        "series": series,
        "bore": bore,
        "rod_diameter": rod,
        "mount": mount,
        "stroke": "300",
        "cushion": "RE",
        "port_code": "S",
        "seal_code": "" if series == "IMH" else "V",
        "rod_style": 1,
        "discount": "0.05",
        "dre": False,
    }


def _create_user(role: str, access_level: str = "standard") -> int:
    with get_session() as session:
        user = User(
            display_name=f"Metric {role} {access_level}",
            role=role,
            access_level=access_level,
            is_active=True,
            approval_status="approved",
        )
        session.add(user)
        session.commit()
        return user.id


def _authenticated_client(app, role: str, access_level: str = "standard"):
    user_id = _create_user(role, access_level)
    authenticated_client = app.test_client()
    with authenticated_client.session_transaction() as session:
        session["user_id"] = user_id
        session["role"] = role
    return authenticated_client


def test_metric_catalog_exposes_only_metric_series(client):
    response = client.get("/api/metric/catalog")

    assert response.status_code == 200
    catalog = response.get_json()
    assert list(catalog["series"]) == ["IH", "IHM", "IMH"]
    assert set(catalog["series"]) == {"IH", "IHM", "IMH"}
    assert "H" not in catalog["series"]
    assert "A" not in catalog["series"]


def test_metric_apis_reject_standard_series(client):
    payload = _metric_payload("IH")
    payload["series"] = "H"

    calculate_response = client.post("/api/metric/calculate", json=payload)
    draft_response = client.post("/api/metric/quote/draft", json=payload)

    assert calculate_response.status_code == 400
    assert draft_response.status_code == 400
    assert "IH, IHM, and IMH" in calculate_response.get_json()["error"]
    assert "IH, IHM, and IMH" in draft_response.get_json()["error"]


@pytest.mark.parametrize("series", ["IH", "IHM", "IMH"])
def test_metric_calculate_supports_each_allowed_series(client, series):
    response = client.post("/api/metric/calculate", json=_metric_payload(series))

    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["model_code"].startswith(f"{series}-")
    assert result["quote_net_each"]


def test_metric_base_price_uses_metric_series_pricing_source(client):
    engine = client.application.extensions["pricing_engine"]
    metric_row = next(
        row
        for row in engine.data.metric_series_pricing
        if row["series_family"] == "IH"
        and row["bore"] == "25"
        and row["rod_diameter"] == "12"
        and "MX0" in row["mount_codes"].split("|")
    )
    conflicting_combined_row = dict(metric_row, base_price="999999")
    engine.data.series_pricing = [conflicting_combined_row]

    selected = engine.data.find_series_price("IH", 25, 12, "MX0")

    assert selected["base_price"] == metric_row["base_price"]


@pytest.mark.parametrize(("seal_code", "expected"), [("P", "47"), ("L", "51"), ("V", None)])
def test_metric_calculate_includes_rod_seal_price(client, seal_code, expected):
    payload = _metric_payload("IH")
    payload["seal_code"] = seal_code

    response = client.post("/api/metric/calculate", json=payload)

    assert response.status_code == 200
    assert response.get_json()["result"]["recommended_rod_seal_price"] == expected


def test_metric_quote_draft_preserves_metric_pricing_and_manual_items(client):
    payload = _metric_payload("IH")
    payload.update(
        {
            "customer_name": "Metric Customer",
            "manual_items": [
                {
                    "part_number": "METRIC-1",
                    "description": "Metric bracket",
                    "quantity": 2,
                    "unit_price": "15.50",
                }
            ],
        }
    )

    response = client.post("/api/metric/quote/draft", json=payload)

    assert response.status_code == 200
    draft = response.get_json()["draft"]
    assert draft["cylinder_inputs"]["series"] == "IH"
    assert draft["pricing_engine_version"] == "Pricing Engine v1.2"
    assert draft["presentation"]["customer_name"] == "Metric Customer"
    assert draft["manual_items"][0]["extended_price"] == "31.00"
    assert draft["price_breakdown"]["recommended_assembly_price"] == "470"


def test_metric_routes_require_their_matching_roles(app):
    anonymous_client = app.test_client()

    employee_response = anonymous_client.get("/employee/metric-quote-entry")
    customer_response = anonymous_client.get("/customer/metric-quote-entry")

    assert employee_response.status_code == 302
    assert customer_response.status_code == 302

    employee_client = _authenticated_client(app, "employee")
    customer_client = _authenticated_client(app, "customer")
    assert employee_client.get("/employee/metric-quote-entry").status_code == 200
    assert customer_client.get("/customer/metric-quote-entry").status_code == 200
    assert 'data-metric-mode="true"' in employee_client.get("/employee/metric-quote-entry").get_data(as_text=True)
    assert 'data-metric-mode="true"' in customer_client.get("/customer/metric-quote-entry").get_data(as_text=True)


def test_existing_dashboard_metric_buttons_use_metric_routes(app):
    employee_client = _authenticated_client(app, "employee")
    customer_client = _authenticated_client(app, "customer")
    admin_client = _authenticated_client(app, "employee", "admin")

    employee_dashboard = employee_client.get("/employee/dashboard").get_data(as_text=True)
    customer_dashboard = customer_client.get("/customer/dashboard").get_data(as_text=True)
    admin_dashboard = admin_client.get("/admin/dashboard").get_data(as_text=True)

    assert "/employee/metric-quote-entry" in employee_dashboard
    assert "/customer/metric-quote-entry" in customer_dashboard
    assert "/employee/metric-quote-entry" in admin_dashboard


def test_standard_calculator_api_remains_available(client):
    payload = _metric_payload("H")
    payload.update({"bore": "2", "rod_diameter": "1", "mount": "MX0", "stroke": "12", "cushion": "NC"})

    response = client.post("/api/calculate", json=payload)

    assert response.status_code == 200
    assert response.get_json()["result"]["model_code"].startswith("H-")
