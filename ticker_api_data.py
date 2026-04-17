#!/usr/bin/env python3
"""Static dataset loading helpers for ticker_api.py."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd


def _logger_or_default(logger: Optional[logging.Logger]) -> logging.Logger:
    return logger or logging.getLogger(__name__)


def load_csv_file(path, index_col: Optional[str] = "ticker", logger: Optional[logging.Logger] = None) -> pd.DataFrame:
    path = Path(path)
    log = _logger_or_default(logger)
    try:
        if not path.exists():
            log.warning("CSV no encontrado: %s", path)
            return pd.DataFrame()
        df = pd.read_csv(path)
        if index_col and index_col in df.columns:
            df[index_col] = df[index_col].astype(str).str.upper().str.strip()
            return df.set_index(index_col)
        return df
    except Exception:
        log.exception("Error cargando CSV: %s", path)
        return pd.DataFrame()


def load_json_file(path, logger: Optional[logging.Logger] = None) -> dict[str, Any]:
    path = Path(path)
    log = _logger_or_default(logger)
    try:
        if not path.exists():
            log.warning("JSON no encontrado: %s", path)
            return {}
        with path.open() as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        log.exception("Error cargando JSON: %s", path)
        return {}


@dataclass
class StaticDatasets:
    docs: Path
    df_5d: pd.DataFrame
    df_ml: pd.DataFrame
    df_fund_us: pd.DataFrame
    df_fund_eu: pd.DataFrame
    df_fund: pd.DataFrame
    df_scores: pd.DataFrame
    df_insiders: pd.DataFrame
    df_reversion: pd.DataFrame
    df_options: pd.DataFrame
    df_prices: pd.DataFrame
    df_positions: pd.DataFrame
    df_industries: pd.DataFrame
    ticker_cache: dict[str, Any]


def load_static_datasets(docs_root="docs", logger: Optional[logging.Logger] = None) -> StaticDatasets:
    docs = Path(docs_root)
    df_5d = load_csv_file(docs / "super_opportunities_5d_complete_with_earnings.csv", logger=logger)
    df_ml = load_csv_file(docs / "ml_scores.csv", logger=logger)
    df_fund_us = load_csv_file(docs / "fundamental_scores.csv", logger=logger)
    df_fund_eu = load_csv_file(docs / "european_fundamental_scores.csv", logger=logger)
    df_fund = pd.concat([df_fund_us, df_fund_eu]) if not df_fund_eu.empty else df_fund_us
    df_scores = load_csv_file(docs / "super_scores_ultimate.csv", logger=logger)
    df_ins_us = load_csv_file(docs / "recurring_insiders.csv", logger=logger)
    df_ins_eu = load_csv_file(docs / "eu_recurring_insiders.csv", logger=logger)
    if not df_ins_us.empty and "market" not in df_ins_us.columns:
        df_ins_us["market"] = "US"
    df_insiders = pd.concat([df_ins_us, df_ins_eu], ignore_index=True) if not df_ins_eu.empty else df_ins_us
    df_reversion = load_csv_file(docs / "mean_reversion_opportunities.csv", logger=logger)
    df_options = load_csv_file(docs / "options_flow.csv", logger=logger)
    df_prices = load_csv_file(docs / "super_opportunities_with_prices.csv", logger=logger)
    df_positions = load_csv_file(docs / "position_sizing.csv", logger=logger)
    df_industries = load_csv_file(docs / "industry_group_rankings.csv", logger=logger)
    ticker_cache = load_json_file(docs / "ticker_data_cache.json", logger=logger)
    return StaticDatasets(
        docs=docs,
        df_5d=df_5d,
        df_ml=df_ml,
        df_fund_us=df_fund_us,
        df_fund_eu=df_fund_eu,
        df_fund=df_fund,
        df_scores=df_scores,
        df_insiders=df_insiders,
        df_reversion=df_reversion,
        df_options=df_options,
        df_prices=df_prices,
        df_positions=df_positions,
        df_industries=df_industries,
        ticker_cache=ticker_cache,
    )


def build_dataset_summary(datasets: StaticDatasets) -> str:
    return (
        f"✅ Cache cargado: {len(datasets.df_5d)} tickers 5D | "
        f"{len(datasets.df_ml)} ML | {len(datasets.df_fund)} fund "
        f"(US:{len(datasets.df_fund_us)}+EU:{len(datasets.df_fund_eu)}) | "
        f"{len(datasets.ticker_cache)} ticker_cache\n"
        f"   Insiders: {len(datasets.df_insiders)} | "
        f"Mean Rev: {len(datasets.df_reversion)} | Options: {len(datasets.df_options)}"
    )
