from __future__ import annotations

import json
from datetime import datetime, timezone

import app.db as db_mod
from app import create_app
from app.db import get_session
from app.models_db import AiUsageDailySnapshot, AiUsageGithubCreditSnapshot, User
from werkzeug.security import generate_password_hash


def test_intraday_snapshot_timestamp_is_displayed_in_eastern_time():
    import app.ai_usage_service as svc

    summer = datetime(2026, 9, 3, 19, 18, 7, tzinfo=timezone.utc)
    winter = datetime(2026, 1, 15, 19, 18, 7, tzinfo=timezone.utc)

    assert svc._eastern_display_timestamp(summer) == "2026-09-03 03:18:07 PM EDT"
    assert svc._eastern_display_timestamp(winter) == "2026-01-15 02:18:07 PM EST"


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
    monkeypatch.setattr(
        svc,
        "_sync_actual_usage_from_github",
        lambda: {"ok": False, "reason": "disabled in tests"},
    )
    return log_path


def _seed_daily_snapshots(rows):
    with get_session() as session:
        session.add_all(rows)
        session.commit()


def _seed_intraday_snapshots(rows):
    with get_session() as session:
        session.add_all(rows)
        session.commit()


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


def test_intraday_spike_correlation_handles_naive_snapshot_bounds(tmp_path, monkeypatch):
    log_path = _empty_routing_log(monkeypatch, tmp_path)
    app, client = _admin_client(tmp_path, monkeypatch)

    import app.ai_usage_service as svc

    _seed_intraday_snapshots(
        [
            AiUsageGithubCreditSnapshot(
                captured_at=datetime(2026, 9, 3, 10, 0, 0),
                cumulative_credits_used=100.0,
                model_breakdown_json="{}",
            ),
            AiUsageGithubCreditSnapshot(
                captured_at=datetime(2026, 9, 3, 11, 0, 0),
                cumulative_credits_used=125.0,
                model_breakdown_json="{}",
            ),
        ]
    )

    log_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-09-03T10:30:00+00:00",
                "task_type": "coding",
                "worker": "AI Coding Worker",
                "outcome": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with app.app_context():
        snapshots = svc._intraday_snapshots_with_deltas()
        assert snapshots[0]["captured_at"].tzinfo == timezone.utc

        correlated = svc._correlated_routing_records(
            svc._read_routing_log(),
            snapshots[0]["captured_at"],
            snapshots[1]["captured_at"],
        )
        assert len(correlated) == 1

        data = svc.get_dashboard_data()
        assert data["intraday_spikes"]

    resp = client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 200


def test_intraday_spike_correlation_normalizes_naive_snapshot_bounds_and_aware_inputs(tmp_path, monkeypatch):
    log_path = _empty_routing_log(monkeypatch, tmp_path)
    app, client = _admin_client(tmp_path, monkeypatch)

    import app.ai_usage_service as svc

    _seed_intraday_snapshots(
        [
            AiUsageGithubCreditSnapshot(
                captured_at=datetime(2026, 9, 3, 10, 0, 0),
                cumulative_credits_used=100.0,
                model_breakdown_json="{}",
            ),
            AiUsageGithubCreditSnapshot(
                captured_at=datetime(2026, 9, 3, 11, 0, 0),
                cumulative_credits_used=125.0,
                model_breakdown_json="{}",
            ),
        ]
    )

    log_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-09-03T10:30:00+00:00",
                "task_type": "coding",
                "worker": "AI Coding Worker",
                "outcome": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with app.app_context():
        snapshots = svc._intraday_snapshots_with_deltas()
        assert snapshots[0]["captured_at"].tzinfo is not None

        aware_start = snapshots[0]["captured_at"].replace(tzinfo=timezone.utc)
        aware_end = snapshots[1]["captured_at"].replace(tzinfo=timezone.utc)
        correlated = svc._correlated_routing_records(svc._read_routing_log(), aware_start, aware_end)
        assert len(correlated) == 1

        data = svc.get_dashboard_data()
        assert data["intraday_spikes"]

    resp = client.get("/employee/admin/ai-usage-dashboard")
    assert resp.status_code == 200


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


def test_dashboard_post_preserves_filters_on_redirect(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    _, client = _admin_client(tmp_path, monkeypatch)

    resp = client.post(
        "/employee/admin/ai-usage-dashboard?start_date=2026-09-02&end_date=2026-09-03",
        data={
            "entry_date": "2026-09-02",
            "credits_used": "150",
            "credits_remaining": "850",
            "note": "manual check-in",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "start_date=2026-09-02" in resp.headers["Location"]
    assert "end_date=2026-09-03" in resp.headers["Location"]


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


def test_dashboard_filters_trend_rows_by_date_range(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    app, _ = _admin_client(tmp_path, monkeypatch)

    import app.ai_usage_service as svc

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "local.agent.md").write_text(
        "---\nname: Local Worker\nmodel: qwen3-coder:30b\n---\n",
        encoding="utf-8",
    )
    (agents_dir / "premium.agent.md").write_text(
        "---\nname: Premium Worker\nmodel: Claude Sonnet 5\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "AGENTS_DIR", agents_dir)

    log_path = tmp_path / "routing_log.jsonl"
    log_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"timestamp": "2026-09-02T10:00:00+00:00", "task_type": "coding", "worker": "Local Worker", "outcome": "success"},
                {"timestamp": "2026-09-02T10:05:00+00:00", "task_type": "coding", "worker": "Local Worker", "outcome": "success"},
                {"timestamp": "2026-09-02T10:10:00+00:00", "task_type": "coding", "worker": "Premium Worker", "outcome": "success"},
                {"timestamp": "2026-09-03T10:00:00+00:00", "task_type": "coding", "worker": "Local Worker", "outcome": "success"},
                {"timestamp": "2026-09-03T10:05:00+00:00", "task_type": "coding", "worker": "Premium Worker", "outcome": "success"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _seed_daily_snapshots(
        [
            AiUsageDailySnapshot(
                snapshot_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
                task_count=10,
                local_task_count=4,
                estimated_savings_credits=20.0,
                baseline_credits_estimate=50.0,
                breakdown_json="{}",
                actual_credits_used_delta=10,
                actual_savings_credits=16.0,
                estimation_error=4.0,
                accuracy_pct=80.0,
            ),
            AiUsageDailySnapshot(
                snapshot_date=datetime(2026, 9, 2, tzinfo=timezone.utc),
                task_count=12,
                local_task_count=5,
                estimated_savings_credits=25.0,
                baseline_credits_estimate=60.0,
                breakdown_json="{}",
                actual_credits_used_delta=11,
                actual_savings_credits=20.0,
                estimation_error=5.0,
                accuracy_pct=84.0,
            ),
            AiUsageDailySnapshot(
                snapshot_date=datetime(2026, 9, 3, tzinfo=timezone.utc),
                task_count=14,
                local_task_count=6,
                estimated_savings_credits=30.0,
                baseline_credits_estimate=70.0,
                breakdown_json="{}",
                actual_credits_used_delta=12,
                actual_savings_credits=24.0,
                estimation_error=6.0,
                accuracy_pct=80.0,
            ),
        ]
    )

    with app.app_context():
        data = svc.get_dashboard_data(datetime(2026, 9, 2, tzinfo=timezone.utc).date(), datetime(2026, 9, 3, tzinfo=timezone.utc).date())

    assert [row["date"].isoformat() for row in data["estimated_vs_actual_trend"]] == ["2026-09-03", "2026-09-02"]
    assert data["estimated_credits_saved"]["value"] == 15.0
    assert data["measured_actual_savings"]["value"] == 44.0
    assert data["estimator_accuracy"]["value"] == 82.0
    assert data["trend_start_date"] == "2026-09-02"
    assert data["trend_end_date"] == "2026-09-03"


def test_dashboard_renders_filter_controls_and_empty_filtered_state(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    _, client = _admin_client(tmp_path, monkeypatch)

    _seed_daily_snapshots(
        [
            AiUsageDailySnapshot(
                snapshot_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
                task_count=10,
                local_task_count=4,
                estimated_savings_credits=20.0,
                baseline_credits_estimate=50.0,
                breakdown_json="{}",
                actual_credits_used_delta=10,
                actual_savings_credits=16.0,
                estimation_error=4.0,
                accuracy_pct=80.0,
            )
        ]
    )

    resp = client.get("/employee/admin/ai-usage-dashboard?start_date=2026-09-03&end_date=2026-09-03")
    assert resp.status_code == 200
    assert b'name="start_date" value="2026-09-03"' in resp.data
    assert b'id="trend-chart"' not in resp.data
    assert b"No finalized days in the selected range." in resp.data


def test_dashboard_ignores_invalid_filter_dates(tmp_path, monkeypatch):
    _empty_routing_log(monkeypatch, tmp_path)
    _, client = _admin_client(tmp_path, monkeypatch)

    resp = client.get("/employee/admin/ai-usage-dashboard?start_date=not-a-date&end_date=2026-99-99")
    assert resp.status_code == 200
    assert b'name="start_date" value=""' in resp.data
    assert b'name="end_date" value=""' in resp.data
