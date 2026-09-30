from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def audit_module(tmp_path, monkeypatch):
    import tools.scope_regression_audit as audit

    app_root = tmp_path / "app"
    audit_root = tmp_path / "scope_audit"
    app_root.mkdir()
    monkeypatch.setattr(audit, "TOOL_ROOT", tmp_path)
    monkeypatch.setattr(audit, "APP_ROOT", app_root)
    monkeypatch.setattr(audit, "AUDIT_ROOT", audit_root)
    monkeypatch.setattr(audit, "BASELINES_ROOT", audit_root / "baselines")
    monkeypatch.setattr(audit, "REPORTS_ROOT", audit_root / "reports")
    return audit, app_root, audit_root


def test_baseline_captures_scope_and_complete_app(audit_module):
    audit, app_root, audit_root = audit_module
    (app_root / "page.html").write_text('<button id="quote">Quote</button>\n', encoding="utf-8")
    (app_root / "page.css").write_text('.quote { color: red; }\n', encoding="utf-8")

    assert audit.create_baseline("Change the quote button text.") == 0

    baseline = next((audit_root / "baselines").iterdir())
    manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
    scope = json.loads((baseline / "scope.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == {"page.html", "page.css"}
    assert scope["approved_scope"] == "Change the quote button text."


def test_audit_reports_modified_added_deleted_and_diff(audit_module):
    audit, app_root, audit_root = audit_module
    (app_root / "changed.html").write_text('<button id="old">Old</button>\n', encoding="utf-8")
    (app_root / "deleted.js").write_text("fetch('/old');\n", encoding="utf-8")
    assert audit.create_baseline("Change changed.html button text.") == 0

    (app_root / "changed.html").write_text('<button id="new">New</button>\n', encoding="utf-8")
    (app_root / "added.css").write_text('.unrelated { color: blue; }\n', encoding="utf-8")
    (app_root / "deleted.js").unlink()

    assert audit.audit(None) == 1
    report = next((audit_root / "reports").glob("*.md")).read_text(encoding="utf-8")
    assert "changed.html" in report
    assert "added.css" in report
    assert "deleted.js" in report
    assert "Old" in report
    assert "New" in report
    assert "SUSPICIOUS" in report


def test_audit_clean_app_returns_pass(audit_module):
    audit, app_root, audit_root = audit_module
    (app_root / "unchanged.py").write_text("def keep():\n    return 1\n", encoding="utf-8")
    assert audit.create_baseline("No application changes.") == 0

    assert audit.audit(None) == 0
    report = next((audit_root / "reports").glob("*.md")).read_text(encoding="utf-8")
    assert "**PASS**" in report
    assert "1 files remain byte-for-byte unchanged." in report


def test_shared_files_report_lists_targets_and_consumers(audit_module):
    audit, app_root, audit_root = audit_module
    (app_root / "shared.css").write_text(".shared { color: red; }\n", encoding="utf-8")
    (app_root / "first.html").write_text('<link rel="stylesheet" href="shared.css">\n', encoding="utf-8")
    (app_root / "second.html").write_text('<link rel="stylesheet" href="shared.css">\n', encoding="utf-8")
    (app_root / "single.html").write_text("shared.css\n", encoding="utf-8")
    (app_root / "history.txt").write_text("shared.css\n", encoding="utf-8")
    audit.SHARED_FILES_REPORT = audit_root / "shared_files_audit.txt"

    assert audit.write_shared_files_report() == 0
    report = audit.SHARED_FILES_REPORT.read_text(encoding="utf-8")
    assert "1. shared.css (3 referencing files)" in report
    assert "a. first.html" in report
    assert "b. second.html" in report
    assert "c. single.html" in report
    assert "history.txt" not in report
