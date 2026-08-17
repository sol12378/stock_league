"""Part 8: XBRLから1株当たり数値(EPS/BPS)を全社ぶん抽出する。

なぜ必要か:
  Price軸を「純利益÷(株数×株価)」で作ると、株数の抽出誤差・株式分割ズレ・
  純利益の科目取り違えが全部そこに乗る。実測で上位20社の30%が異常値になった。
  XBRLが自ら報告している1株当たり当期純利益(EPS)と1株当たり純資産(BPS)は
  株数に依存せず、提出時点で分割も反映済みなので、こちらを正とする。

  益回り E/P = EPS / 株価      純資産倍率の逆数 B/M = BPS / 株価

対象: 各社の最新提出分(PITパネルの doc_id)。速度のため XML パースせず
      対象タグだけ正規表現で抜く。

出力: work/new_4axis_screen/out/per_share_values.csv
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
XBRL_DIR = ROOT / "data/raw/edinet/xbrl"
PANEL = ROOT / "work/phase2_perfect_final_break/point_in_time_panel/point_in_time_feature_panel_with_filters.csv"

# 優先順に試す。SummaryOfBusinessResults 系は主要な経営指標等の表から来る
EPS_TAGS = [
    "BasicEarningsLossPerShareSummaryOfBusinessResults",
    "BasicEarningsPerShareSummaryOfBusinessResults",
    "BasicEarningsLossPerShare",
    "BasicEarningsPerShare",
]
BPS_TAGS = [
    "NetAssetsPerShareSummaryOfBusinessResults",
    "NetAssetsPerShare",
]
DPS_TAGS = [
    "DividendPaidPerShareSummaryOfBusinessResults",
]


def _compile(tags: list[str]) -> list[tuple[str, re.Pattern[bytes]]]:
    out = []
    for t in tags:
        # <jpcrp_cor:TAG contextRef="..." ...>値</...:TAG>
        pat = re.compile(
            rb"<[\w\-]+:" + t.encode() + rb"\s([^>]*?)>([^<]*)</[\w\-]+:" + t.encode() + rb">"
        )
        out.append((t, pat))
    return out


EPS_PATS, BPS_PATS, DPS_PATS = _compile(EPS_TAGS), _compile(BPS_TAGS), _compile(DPS_TAGS)
CTX = re.compile(rb'contextRef="([^"]+)"')


def _pick(blob: bytes, pats: list[tuple[str, re.Pattern[bytes]]]) -> tuple[float | None, str | None]:
    """CurrentYear の文脈を優先して1件返す。"""
    for tag, pat in pats:
        best = None
        for m in pat.finditer(blob):
            attrs, raw = m.group(1), m.group(2)
            ctx_m = CTX.search(attrs)
            ctx = ctx_m.group(1).decode(errors="ignore") if ctx_m else ""
            # 連結・当期を優先。前期(Prior)や非連結(NonConsolidated)は後回し
            if "Prior" in ctx:
                continue
            rank = 0 if "CurrentYear" in ctx else 1
            rank += 2 if "NonConsolidated" in ctx else 0
            try:
                val = float(raw.decode().strip().replace(",", "").replace("△", "-"))
            except (ValueError, UnicodeDecodeError):
                continue
            if best is None or rank < best[0]:
                best = (rank, val, tag)
        if best is not None:
            return best[1], best[2]
    return None, None


def main() -> None:
    panel = pd.read_csv(PANEL, dtype={"code": str}, low_memory=False,
                        usecols=["code", "doc_id", "fiscal_year"])
    latest = panel.sort_values("fiscal_year").groupby("code", as_index=False).last()
    print(f"対象 {len(latest)} 社")

    rows = []
    for r in tqdm(latest.itertuples(index=False), total=len(latest), desc="xbrl"):
        path = XBRL_DIR / f"{r.doc_id}.zip"
        if not path.exists():
            rows.append({"code": r.code, "eps": None, "bps": None, "dps": None,
                         "source": "zip_missing"})
            continue
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
                if not names:
                    raise KeyError("no PublicDoc xbrl")
                blob = z.read(names[0])
        except Exception as exc:  # 壊れたzip・想定外の構成
            rows.append({"code": r.code, "eps": None, "bps": None, "dps": None,
                         "source": f"error:{type(exc).__name__}"})
            continue
        eps, eps_tag = _pick(blob, EPS_PATS)
        bps, bps_tag = _pick(blob, BPS_PATS)
        dps, _ = _pick(blob, DPS_PATS)
        rows.append({"code": r.code, "fiscal_year": r.fiscal_year, "eps": eps, "bps": bps,
                     "dps": dps, "eps_tag": eps_tag, "bps_tag": bps_tag, "source": "ok"})

    out = pd.DataFrame(rows)
    out.to_csv(OUT / "per_share_values.csv", index=False)
    print()
    print("EPS取得:", int(out["eps"].notna().sum()), "/", len(out))
    print("BPS取得:", int(out["bps"].notna().sum()), "/", len(out))
    print("DPS取得:", int(out["dps"].notna().sum()), "/", len(out))
    print(out["source"].value_counts().to_string())


if __name__ == "__main__":
    main()
