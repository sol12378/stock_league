from __future__ import annotations

import argparse
import json
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from src.config import AppConfig, load_config
from src.utils.logging import setup_logger


EDINET_BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
DOCUMENT_COLUMNS = [
    "code",
    "sec_code",
    "doc_id",
    "edinet_code",
    "filer_name",
    "submit_date",
    "period_start",
    "period_end",
    "doc_description",
    "ordinance_code",
    "form_code",
]


class EdinetAuthenticationError(RuntimeError):
    """Raised when EDINET rejects the configured subscription key."""


EdinetLimit = int | str | None


def normalize_edinet_limit(value: EdinetLimit) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("EDINET limit must be positive or 'all'.")
        return value
    clean = str(value).strip().lower()
    if clean == "all":
        return None
    try:
        parsed = int(clean)
    except ValueError as exc:
        raise ValueError("EDINET limit must be a positive integer or 'all'.") from exc
    if parsed <= 0:
        raise ValueError("EDINET limit must be positive or 'all'.")
    return parsed


def select_edinet_codes(source: pd.DataFrame, limit: EdinetLimit) -> list[str]:
    normalized_limit = normalize_edinet_limit(limit)
    codes = source["code"].dropna().astype(str)
    if normalized_limit is not None:
        codes = codes.head(normalized_limit)
    return codes.tolist()


def _api_key_params(config: AppConfig) -> dict[str, str]:
    return {"Subscription-Key": config.edinet_api_key} if config.edinet_api_key else {}


def _api_key_headers(config: AppConfig) -> dict[str, str]:
    # ESE140206.pdf specifies Subscription-Key as a request parameter.
    return {}


def iter_dates_desc(lookback_days: int, end_date: date | None = None) -> list[date]:
    end_date = end_date or date.today()
    return [end_date - timedelta(days=i) for i in range(lookback_days + 1)]


def get_documents_for_date(
    session: requests.Session,
    config: AppConfig,
    target_date: date,
    cache_dir: Path,
) -> list[dict[str, object]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"documents_{target_date:%Y-%m-%d}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("StatusCode") == 401:
            # Ignore stale bad-key caches so a corrected key can overwrite them later.
            pass
        elif "results" in cached:
            return cached.get("results", [])

    params = {"date": target_date.isoformat(), "type": 2}
    params.update(_api_key_params(config))
    response = session.get(
        f"{EDINET_BASE_URL}/documents.json",
        params=params,
        headers=_api_key_headers(config),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("StatusCode") == 401:
        raise EdinetAuthenticationError(str(payload.get("message", "invalid subscription key")))
    if payload.get("StatusCode") not in {None, 200} and "results" not in payload:
        raise RuntimeError(str(payload))
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload.get("results", [])


def _is_annual_report(item: dict[str, object]) -> bool:
    doc_type = str(item.get("docTypeCode") or "")
    description = str(item.get("docDescription") or "")
    return doc_type == "120" and "訂正" not in description


def collect_annual_documents(
    config: AppConfig,
    target_codes: set[str],
    lookback_days: int = 1300,
    docs_per_company: int = 3,
    sleep_seconds: float = 0.2,
) -> pd.DataFrame:
    logger = setup_logger("fetch_edinet", config.logs_dir)
    session = requests.Session()
    rows: list[dict[str, object]] = []
    counts = {code: 0 for code in target_codes}
    cache_dir = config.edinet_raw_dir / "documents_json"
    status_path = config.logs_dir / "edinet_api_status.csv"
    authentication_failed = False

    for target_date in tqdm(iter_dates_desc(lookback_days), desc="edinet documents"):
        try:
            documents = get_documents_for_date(session, config, target_date, cache_dir)
        except EdinetAuthenticationError as exc:
            logger.error("EDINET authentication failed: %s", exc)
            authentication_failed = True
            pd.DataFrame(
                [
                    {
                        "status": "authentication_failed",
                        "message": str(exc),
                        "hint": "Check the EDINET API key shown on the official API key issuance screen.",
                    }
                ]
            ).to_csv(status_path, index=False)
            break
        except Exception as exc:
            logger.warning("EDINET documents failed for %s: %s", target_date, exc)
            time.sleep(sleep_seconds)
            continue

        for item in documents:
            if not _is_annual_report(item):
                continue
            sec_code = str(item.get("secCode") or "").strip()
            code = sec_code[:4]
            if code not in target_codes or counts.get(code, 0) >= docs_per_company:
                continue
            rows.append(
                {
                    "code": code,
                    "sec_code": sec_code,
                    "doc_id": item.get("docID"),
                    "edinet_code": item.get("edinetCode"),
                    "filer_name": item.get("filerName"),
                    "submit_date": item.get("submitDateTime"),
                    "period_start": item.get("periodStart"),
                    "period_end": item.get("periodEnd"),
                    "doc_description": item.get("docDescription"),
                    "ordinance_code": item.get("ordinanceCode"),
                    "form_code": item.get("formCode"),
                }
            )
            counts[code] = counts.get(code, 0) + 1
        if rows and all(counts.get(code, 0) >= docs_per_company for code in target_codes):
            break
        time.sleep(sleep_seconds)

    docs = pd.DataFrame(rows, columns=DOCUMENT_COLUMNS).drop_duplicates("doc_id") if rows else pd.DataFrame(columns=DOCUMENT_COLUMNS)
    if not docs.empty:
        docs = docs.sort_values(["code", "submit_date"], ascending=[True, False])
    docs.to_csv(config.data_processed_dir / "edinet_documents.csv", index=False)
    missing = pd.DataFrame(
        [
            {
                "code": code,
                "documents_found": counts.get(code, 0),
                "missing_reason": "no_annual_report_found"
                if counts.get(code, 0) == 0
                else "incomplete_period_coverage",
            }
            for code in sorted(target_codes)
            if counts.get(code, 0) < docs_per_company
        ]
    )
    universe_path = config.data_processed_dir / "universe.csv"
    if not missing.empty and universe_path.exists():
        universe = pd.read_csv(universe_path, dtype={"code": str})
        name_cols = [c for c in ["code", "ticker", "company_name", "company_name_ja"] if c in universe.columns]
        missing = missing.merge(universe[name_cols].drop_duplicates("code"), on="code", how="left")
    missing.to_csv(config.logs_dir / "edinet_missing_companies.csv", index=False)
    if not authentication_failed:
        pd.DataFrame(
            [
                {
                    "status": "ok",
                    "message": "",
                    "documents": len(docs),
                    "companies_requested": len(target_codes),
                    "companies_with_documents": sum(1 for count in counts.values() if count > 0),
                    "companies_incomplete": len(missing),
                }
            ]
        ).to_csv(status_path, index=False)
    logger.info("Collected %s EDINET annual report document rows", len(docs))
    return docs


def is_valid_xbrl_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except zipfile.BadZipFile:
        return False


def download_xbrl_zip(
    session: requests.Session,
    config: AppConfig,
    doc_id: str,
    output_path: Path,
) -> bool:
    if is_valid_xbrl_zip(output_path):
        return True
    params = {"type": 1}
    params.update(_api_key_params(config))
    response = session.get(
        f"{EDINET_BASE_URL}/documents/{doc_id}",
        params=params,
        headers=_api_key_headers(config),
        timeout=60,
    )
    if response.status_code != 200 or not response.content:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return True


def fetch_edinet_for_codes(
    config: AppConfig,
    codes: list[str],
    lookback_days: int = 1300,
    docs_per_company: int = 3,
    sleep_seconds: float = 0.2,
) -> pd.DataFrame:
    logger = setup_logger("fetch_edinet", config.logs_dir)
    target_codes = {str(code).zfill(4) if str(code).isdigit() else str(code) for code in codes}
    docs = collect_annual_documents(
        config,
        target_codes=target_codes,
        lookback_days=lookback_days,
        docs_per_company=docs_per_company,
        sleep_seconds=sleep_seconds,
    )
    if docs.empty:
        return docs

    session = requests.Session()
    status_rows: list[dict[str, object]] = []
    for row in tqdm(docs.to_dict("records"), desc="edinet xbrl"):
        doc_id = str(row["doc_id"])
        zip_path = config.edinet_raw_dir / "xbrl" / f"{doc_id}.zip"
        try:
            ok = download_xbrl_zip(session, config, doc_id, zip_path)
        except Exception as exc:
            ok = False
            status_rows.append({"doc_id": doc_id, "zip_path": zip_path, "ok": ok, "error": str(exc)})
        else:
            status_rows.append({"doc_id": doc_id, "zip_path": zip_path, "ok": ok, "error": ""})
        time.sleep(sleep_seconds)

    status = pd.DataFrame(status_rows)
    status.to_csv(config.logs_dir / "edinet_download_status.csv", index=False)
    logger.info("Downloaded %s/%s EDINET XBRL zips", int(status["ok"].sum()), len(status))
    return docs.merge(status, on="doc_id", how="left")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", default="300")
    parser.add_argument("--lookback-days", type=int, default=1300)
    parser.add_argument("--docs-per-company", type=int, default=3)
    args = parser.parse_args()
    config = load_config()

    scores_path = config.data_processed_dir / "scores.csv"
    universe_path = config.data_processed_dir / "universe.csv"
    if scores_path.exists():
        source = pd.read_csv(scores_path, dtype={"code": str}).sort_values(
            "adjusted_bb_score", ascending=False
        )
    else:
        source = pd.read_csv(universe_path, dtype={"code": str})
    codes = select_edinet_codes(source, args.limit)
    fetch_edinet_for_codes(
        config,
        codes=codes,
        lookback_days=args.lookback_days,
        docs_per_company=args.docs_per_company,
    )


if __name__ == "__main__":
    main()
