#!/usr/bin/env python3
"""Tests for extracted ticker_api support modules."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ticker_api_config import build_cors_origins, load_runtime_config
from ticker_api_data import load_csv_file, load_json_file


def test_runtime_config_defaults_to_safe_dev_mode():
    cfg = load_runtime_config({})
    assert cfg.is_production is False
    assert cfg.auth_bypass_enabled is True
    assert cfg.require_supabase_auth is False
    assert "http://localhost:5173" in cfg.cors_origins


def test_runtime_config_production_requires_auth():
    cfg = load_runtime_config({
        "FLASK_ENV": "production",
        "SUPABASE_URL": "https://example.supabase.co",
        "ALLOWED_ORIGINS": "https://app.example.com",
    })
    assert cfg.is_production is True
    assert cfg.auth_bypass_enabled is False
    assert cfg.require_supabase_auth is True
    assert cfg.cors_origins == ["https://app.example.com"]
    assert cfg.jwks_client is not None


def test_build_cors_origins_keeps_configured_values():
    origins = build_cors_origins({"ALLOWED_ORIGINS": "https://a.test, https://b.test"})
    assert origins[:2] == ["https://a.test", "https://b.test"]


def test_load_csv_file_indexes_ticker_column(tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("ticker,value\nmsft,1\n")
    df = load_csv_file(csv_path)
    assert list(df.index) == ["MSFT"]
    assert df.loc["MSFT", "value"] == 1


def test_load_json_file_reads_objects(tmp_path: Path):
    json_path = tmp_path / "sample.json"
    json_path.write_text('{"ok": true}')
    data = load_json_file(json_path)
    assert data == {"ok": True}


def test_loaders_handle_missing_files(tmp_path: Path):
    assert load_csv_file(tmp_path / "missing.csv").empty
    assert load_json_file(tmp_path / "missing.json") == {}
