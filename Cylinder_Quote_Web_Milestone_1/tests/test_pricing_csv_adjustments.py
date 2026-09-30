from __future__ import annotations

import csv
import shutil

import app.pricing_csv_service as pricing_csv_service
import openpyxl
import pytest
from app.pricing_csv_service import PricingCsvError


def _copy_data_folder(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for source in pricing_csv_service.PRICING_DATA_DIRECTORY.glob("*.xlsx"):
        if source.name.startswith("~$"):
            continue
        shutil.copy2(source, data_dir / source.name)
    return data_dir


def _copy_pricing_mirrors(tmp_path):
    mirror_dir = tmp_path / "pricing_file_mirrors"
    mirror_dir.mkdir()
    for source in pricing_csv_service.PRICING_MIRROR_DIRECTORY.glob("*.xlsx"):
        shutil.copy2(source, mirror_dir / source.name)
    return mirror_dir


def test_xlsx_price_edit_preserves_structure_and_records_history(tmp_path, monkeypatch):
    data_dir = _copy_data_folder(tmp_path)
    history_path = tmp_path / "pricing_history.txt"
    monkeypatch.setattr(pricing_csv_service, "PRICING_DATA_DIRECTORY", data_dir)
    monkeypatch.setattr(pricing_csv_service, "PRICING_HISTORY_PATH", history_path)
    monkeypatch.setattr(pricing_csv_service, "_reload_runtime_pricing", lambda: None)

    document = pricing_csv_service.read_pricing_xlsx("metric_series_pricing_inprogress - Copy.xlsx")
    original_headers = document["headers"]
    document["rows"][0]["stroke_rate"] = "12.5"

    result = pricing_csv_service.save_pricing_xlsx(
        document["filename"],
        document["headers"],
        document["rows"],
        actor="admin@test",
    )

    assert result["changed_cells"] == 1
    workbook = openpyxl.load_workbook(data_dir / "metric_series_pricing_inprogress - Copy.xlsx", data_only=True, read_only=True)
    saved = workbook.active
    assert [cell.value for cell in saved[1]] == original_headers
    assert saved[2][original_headers.index("stroke_rate")].value == 12.5
    workbook.close()
    assert "metric_series_pricing_inprogress - Copy.xlsx" in history_path.read_text(encoding="utf-8")


def test_xlsx_price_edit_rejects_structural_changes(tmp_path, monkeypatch):
    data_dir = _copy_data_folder(tmp_path)
    monkeypatch.setattr(pricing_csv_service, "PRICING_DATA_DIRECTORY", data_dir)
    monkeypatch.setattr(pricing_csv_service, "_reload_runtime_pricing", lambda: None)

    document = pricing_csv_service.read_pricing_xlsx("metric_series_pricing_inprogress - Copy.xlsx")
    document["rows"][0]["series_family"] = "CHANGED"

    with pytest.raises(PricingCsvError, match="Only pricing columns"):
        pricing_csv_service.save_pricing_xlsx(
            document["filename"],
            document["headers"],
            document["rows"],
            actor="admin@test",
        )


def test_xlsx_mirror_edit_preserves_runtime_source_and_records_history(tmp_path, monkeypatch):
    mirror_dir = _copy_pricing_mirrors(tmp_path)
    history_path = tmp_path / "pricing_history.txt"
    source_path = pricing_csv_service.PRICING_DATA_DIRECTORY / "standard_series_pricing.xlsx"
    source_bytes = source_path.read_bytes()
    monkeypatch.setattr(pricing_csv_service, "PRICING_MIRROR_DIRECTORY", mirror_dir)
    monkeypatch.setattr(pricing_csv_service, "PRICING_HISTORY_PATH", history_path)

    document = pricing_csv_service.read_pricing_file("standard_series_pricing.xlsx")
    original_price = document["rows"][0]["base_price"]
    document["rows"][0]["base_price"] = str(int(float(original_price)) + 1)

    result = pricing_csv_service.save_pricing_xlsx(
        document["filename"],
        document["headers"],
        document["rows"],
        actor="admin@test",
    )

    assert result["changed_cells"] == 1
    assert source_path.read_bytes() == source_bytes
    workbook = openpyxl.load_workbook(mirror_dir / "standard_series_pricing.xlsx", data_only=True, read_only=True)
    assert workbook["series_pricing"]["P2"].value == int(float(original_price)) + 1
    workbook.close()
    assert "XLSX mirror" in history_path.read_text(encoding="utf-8")


def test_pricing_file_list_hides_series_row_rates():
    filenames = {file["filename"] for file in pricing_csv_service.list_pricing_csvs()}

    assert "series_row_rates.xlsx" not in filenames
    assert "series_pricing.xlsx" not in filenames

    runtime_files = pricing_csv_service.list_runtime_series_pricing_files()
    assert [(file["filename"], file["row_count"]) for file in runtime_files] == [
        ("standard_series_pricing.xlsx", 458),
        ("metric_series_pricing.xlsx", 156),
    ]


def test_standard_series_pricing_display_hides_sources_and_reorders_columns():
    document = pricing_csv_service.read_pricing_xlsx("standard_series_pricing.xlsx")
    headers = document["display_headers"]

    assert headers.index("mount_codes") == headers.index("series_aliases") + 1
    assert headers.index("base_price") == headers.index("cushion_per_end") + 1
    assert document["display_labels"]["stroke_rate"] == "Stroke rate per in"
    assert "stroke_unit" not in headers
    assert not any("source" in header.lower() or "formula" in header.lower() for header in headers)
