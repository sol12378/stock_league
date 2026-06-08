from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    jpx_listed_companies_path: Path
    edinet_api_key: str
    backtest_years: int
    total_capital: int
    portfolio_size: int
    max_weight: float
    topix_proxy: str
    nikkei: str
    edinet_limit: str
    data_raw_dir: Path
    data_processed_dir: Path
    prices_raw_dir: Path
    edinet_raw_dir: Path
    reports_figures_dir: Path
    reports_tables_dir: Path
    reports_draft_dir: Path
    logs_dir: Path

    @classmethod
    def load(cls) -> "AppConfig":
        load_dotenv(ROOT_DIR / ".env")
        jpx_path = Path(_env("JPX_LISTED_COMPANIES_PATH", "docs/data_e.xls"))
        if not jpx_path.is_absolute():
            jpx_path = ROOT_DIR / jpx_path
        return cls(
            root_dir=ROOT_DIR,
            jpx_listed_companies_path=jpx_path,
            edinet_api_key=_env("EDINET_API_KEY", ""),
            backtest_years=_env_int("BACKTEST_YEARS", 5),
            total_capital=_env_int("TOTAL_CAPITAL", 5_000_000),
            portfolio_size=_env_int("PORTFOLIO_SIZE", 20),
            max_weight=_env_float("MAX_WEIGHT", 0.08),
            topix_proxy=_env("TOPIX_PROXY", "1306.T"),
            nikkei=_env("NIKKEI", "^N225"),
            edinet_limit=_env("EDINET_LIMIT", "300").lower(),
            data_raw_dir=ROOT_DIR / "data" / "raw",
            data_processed_dir=ROOT_DIR / "data" / "processed",
            prices_raw_dir=ROOT_DIR / "data" / "raw" / "prices",
            edinet_raw_dir=ROOT_DIR / "data" / "raw" / "edinet",
            reports_figures_dir=ROOT_DIR / "reports" / "figures",
            reports_tables_dir=ROOT_DIR / "reports" / "tables",
            reports_draft_dir=ROOT_DIR / "reports" / "draft",
            logs_dir=ROOT_DIR / "logs",
        )

    def ensure_dirs(self) -> None:
        for path in [
            self.data_raw_dir / "jpx",
            self.prices_raw_dir,
            self.edinet_raw_dir,
            self.data_processed_dir,
            self.reports_figures_dir,
            self.reports_tables_dir,
            self.reports_draft_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    config = AppConfig.load()
    config.ensure_dirs()
    return config
