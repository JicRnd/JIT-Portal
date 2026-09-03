from __future__ import annotations

import json

import app.db as db_mod
from app import create_app
from app.db import get_session
from app.models_db import User
from werkzeug.security import generate_password_hash


def _reset_engines() -> None:
    db_mod._engine = None
    db_mod._accounts_engine = None
    db_mod._quotes_engine = None
    db_mod._orders_engine = None
    db_mod._pricing_engine = None
    db_mod._Session = None


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ACCOUNTS_DATABASE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("QUOTES_DATABASE_PATH", str(tmp_path / "quotes.db"))
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(tmp_path / "orders.db"))
    monkeypatch.setenv("PRICING_DATABASE_PATH", str(tmp_path / "Pricing.db"))
    _reset_engines()
    return create_app()


def _admin_client(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    app.testing = True
    with get_session() as session:
        session.add(
            User(
                display_name="Ops Admin",
                username="opsadmin@example.com",
                email="opsadmin@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                access_level="admin",
                is_active=True,
            )
        )
        session.add(
            User(
                display_name="Standard Employee",
                username="standard2@example.com",
                email="standard2@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                access_level="standard",
                is_active=True,
            )
        )
        session.commit()

    client = app.test_client()
    client.post("/employee/login", data={"identity": "opsadmin@example.com", "password": "pw"})
    return app, client


def _standard_client(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    app.testing = True
    with get_session() as session:
        session.add(
            User(
                display_name="Standard Employee",
                username="standard@example.com",
                email="standard@example.com",
                password_hash=generate_password_hash("pw"),
                role="employee",
                access_level="standard",
                is_active=True,
            )
        )
        session.commit()

    client = app.test_client()
    client.post("/employee/login", data={"identity": "standard@example.com", "password": "pw"})
    return app, client


def _empty_routing_log(monkeypatch, tmp_path):
    """Point the service at an isolated, empty routing log for deterministic tests."""
    import app.ai_usage_service as svc
    log_path = tmp_path / "routing_log.jsonl"
    monkeypatch.setattr(svc, "ROUTING_LOG_PATH", log_path)
    return log_path


def test_dashboard_requires_admin(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    _, client = _standard_client(tmp_path, monkeypatch)
    resp = client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 302

    unauth_app = _make_app(tmp_path, monkeypatch)
    unauth_client = unauth_app.test_client()
    resp = unauth_client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 302


def test_dashboard_renders_with_zero_and_one_log_records(tmp_path, monkeypatch):
    log_path = _empty_routing_log(monkeypatch, tmp_path)
    _, client = _admin_client(tmp_path, monkeypatch)

    resp = client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 200
    assert b"AI Usage Dashboard" in resp.data
    assert b"insufficient data" in resp.data

    log_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-09-02T19:18:07+00:00",
                "task_type": "smoke-test",
                "worker": "AI Coding Worker",
                "outcome": "success",
                "note": "initial wiring test",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    resp = client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 200
    assert b"AI Coding Worker" in resp.data


def test_submitting_valid_credit_entry_persists_and_reflects_on_next_get(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    _, client = _admin_client(tmp_path, monkeypatch)

    resp = client.post(
        "/employee/admin/ai-usage-dashboard",
        data={
            "entry_date": "2026-09-02",
            "credits_used": "150",
            "credits_remaining": "850",
            "note": "manual check-in",
        },
    )
    assert resp.status_code == 302

    resp = client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 200
    assert b"150" in resp.data
    assert b"manual check-in" in resp.data


def test_invalid_credit_entry_rejected(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    _, client = _admin_client(tmp_path, monkeypatch)

    resp = client.post(
        "/employee/admin/ai-usage-dashboard",
        data={"entry_date": "2026-09-02", "credits_used": "-5", "credits_remaining": "", "note": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"must not be negative" in resp.data

    from app.models_db import AiUsageCreditEntry
    with get_session() as session:
        assert session.query(AiUsageCreditEntry).count() == 0


def test_estimate_is_reconciled_against_actual_credits_and_recalibrates(tmp_path, monkeypatch):
    """Yesterday's live estimate is frozen, then measured against a real credit
    entry the next day, and the affected class's calibration is nudged."""
    import app.ai_usage_service as svc

    log_path = _empty_routing_log(monkeypatch, tmp_path)
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "local.agent.md").write_text(
        "---\nname: Local Worker\nmodel: qwen3-coder:30b\n---\n", encoding="utf-8"
    )
    (agents_dir / "premium.agent.md").write_text(
        "---\nname: Premium Worker\nmodel: Claude Sonnet 5\n---\n", encoding="utf-8"
    )
    monkeypatch.setattr(svc, "AGENTS_DIR", agents_dir)

    yesterday = "2026-09-01"
    log_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "timestamp": f"{yesterday}T10:0{i}:00+00:00",
                    "task_type": "coding",
                    "worker": "Local Worker" if i < 3 else "Premium Worker",
                    "outcome": "success",
                }
            )
            for i in range(4)
        )
        + "\n",
        encoding="utf-8",
    )

    app, client = _admin_client(tmp_path, monkeypatch)

    with app.app_context():
        # First read freezes yesterday's estimate; no credit entries exist yet.
        data = svc.get_dashboard_data()
        trend = data["estimated_vs_actual_trend"]
        assert len(trend) == 1
        assert trend[0]["date"].isoformat() == yesterday
        assert trend[0]["actual_savings"] is None
        assert data["measured_actual_savings"]["value"] is None

    svc.add_credit_entry("2026-08-31", "100", None, None)
    svc.add_credit_entry(yesterday, "105", None, None)

    with app.app_context():
        data = svc.get_dashboard_data()
        trend = data["estimated_vs_actual_trend"]
        # 1 premium task cost 5 credits total -> observed rate 5/task,
        # applied to the 3 local tasks that were avoided that day.
        assert trend[0]["actual_savings"] == 15.0
        assert trend[0]["accuracy_pct"] is not None
        assert data["measured_actual_savings"]["value"] == 15.0
        assert data["measured_actual_savings"]["is_estimate"] is False

        calibration = {(row["task_type"], row["worker"]): row for row in data["class_calibration"]}
        assert calibration[("coding", "Local Worker")]["calibrated_cost_per_task"] == 5.0
        assert calibration[("coding", "Local Worker")]["sample_days"] == 1

        # Re-running must not mutate the already-reconciled snapshot.
        data_again = svc.get_dashboard_data()
        assert data_again["estimated_vs_actual_trend"][0]["actual_savings"] == 15.0
