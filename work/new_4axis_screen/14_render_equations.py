"""Part 14: レポートに載せる数式を Computer Modern で組版して画像にする。

docx には数式をそのまま書けないので、matplotlib の mathtext(フォントセットは cm＝
LaTeX と同じ Computer Modern)でレンダリングして貼り込む。

表記の方針は docs/explain_docs/phase1_buffett_methodology_report.tex に合わせる。
  - 変数でない文字列(指標名・関数名)は \\mathrm で立体にする
  - 添字 i は企業、k は成分を表す斜体の変数
  - 括弧は \\left( \\right) でサイズを合わせる
  - 定義は := 、等式は =
  - 日本語は数式に入れず、記号表で対応づける

出力: work/new_4axis_screen/out/eq/*.png と eq_index.json
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["mathtext.fontset"] = "cm"
# default は "it"（既定）のままにする。変数は斜体、\mathrm で囲んだ指標名は立体、
# という LaTeX の慣行どおりに出したいため、"regular" で上書きしてはいけない。
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
EQ_DIR = OUT / "eq"
EQ_DIR.mkdir(parents=True, exist_ok=True)

DPI = 300
FONTSIZE = 16
MAX_W_PX = 600          # docx 上での最大表示幅

DEF = r"\;:\!=\;"       # := の前後を詰めた定義記号

EQUATIONS: dict[str, str] = {
    # ---------- 共通 ----------
    "pctrank": r"\mathrm{pct}(x_{k,i})" + DEF +
               r"100\times\frac{\mathrm{rank}\left(x_{k,i}\right)}{N_k}",
    "axis_mean": r"\mathrm{Axis}_i" + DEF +
                 r"\frac{1}{\left|K_i\right|}\sum_{k\in K_i}\mathrm{pct}\left(x_{k,i}\right)",
    "total": r"\mathrm{Total}_i\;=\;0.25\,\mathrm{Moat}_i+0.25\,\mathrm{Chg}_i"
             r"+0.25\,\mathrm{Fut}_i+0.25\,\mathrm{Pri}_i",
    "effective_weight": r"w^{\mathrm{eff}}_a\;=\;"
                        r"\frac{\mathrm{Cov}\left(0.25\,A_{a},\;\mathrm{Total}\right)}"
                        r"{\mathrm{Var}\left(\mathrm{Total}\right)},"
                        r"\qquad \sum_a w^{\mathrm{eff}}_a=1",
    "alloc": r"n_i\;=\;\mathrm{round}\!\left(\frac{0.05\,C}{100\,P_i}\right),"
             r"\qquad \mathrm{Cost}_i\;=\;100\,n_i P_i\;\leq\;0.08\,C",
    # ---------- 既存式版 ①Moat (QMJ) ----------
    "qmj": r"\mathrm{Moat}_i" + DEF +
           r"\frac{1}{6}\left[z(\mathrm{GPOA}_i)+z(\mathrm{ROE}_i)+z(\mathrm{ROA}_i)"
           r"+z(\mathrm{CFOA}_i)+z(\mathrm{GMAR}_i)+z(\mathrm{ACC}_i)\right]",
    "gpoa": r"\mathrm{GPOA}_i" + DEF + r"\frac{\mathrm{GP}_i}{\mathrm{TA}_i}"
            r"\;=\;\frac{\mathrm{Sales}_i-\mathrm{COGS}_i}{\mathrm{TA}_i}",
    "roe_roa": r"\mathrm{ROE}_i" + DEF + r"\frac{\mathrm{NI}_i}{\mathrm{BE}_i},"
               r"\qquad \mathrm{ROA}_i" + DEF + r"\frac{\mathrm{NI}_i}{\mathrm{TA}_i}",
    "cfoa_gmar": r"\mathrm{CFOA}_i" + DEF + r"\frac{\mathrm{CFO}_i}{\mathrm{TA}_i},"
                 r"\qquad \mathrm{GMAR}_i" + DEF + r"\frac{\mathrm{GP}_i}{\mathrm{Sales}_i}",
    "acc": r"\mathrm{ACC}_i" + DEF + r"-\,\frac{\mathrm{NI}_i-\mathrm{CFO}_i}{\mathrm{TA}_i}",
    "zscore_rank": r"z(x_i)" + DEF +
                   r"\frac{\mathrm{rank}(x_i)-\overline{\mathrm{rank}(x)}}"
                   r"{\mathrm{sd}\left(\mathrm{rank}(x)\right)}",
    # ---------- 既存式版 ②Change (Piotroski) ----------
    "fscore": r"\mathrm{Chg}^{\,\mathrm{raw}}_i" + DEF + r"\sum_{k=1}^{9}s_{k,i},"
              r"\qquad s_{k,i}\in\{0,1\}",
    "fscore_pct": r"\mathrm{Chg}_i\;=\;\mathrm{pct}\!\left(\mathrm{Chg}^{\,\mathrm{raw}}_i\right)",
    # ---------- 既存式版 ③Future (CLS) ----------
    "cls": r"\mathrm{Fut}_i" + DEF +
           r"\frac{1}{2}\left[\mathrm{pct}\!\left(\frac{\mathrm{RD}_i}{\mathrm{MC}_i}\right)"
           r"+\mathrm{pct}\!\left(\frac{\mathrm{RD}_i}{\mathrm{Sales}_i}\right)\right]",
    # ---------- 既存式版 ④Price ----------
    "price": r"\mathrm{Pri}_i" + DEF +
             r"\frac{1}{3}\left[\mathrm{pct}\!\left(\mathrm{EP}_i\right)"
             r"+\mathrm{pct}\!\left(\mathrm{BM}_i\right)"
             r"+\mathrm{pct}\!\left(\mathrm{EY}_i\right)\right]",
    "ep_bm": r"\mathrm{EP}_i" + DEF + r"\frac{\mathrm{NI}_i}{\mathrm{MC}_i},"
             r"\qquad \mathrm{BM}_i" + DEF + r"\frac{\mathrm{BE}_i}{\mathrm{MC}_i}",
    "ey_ev": r"\mathrm{EY}_i" + DEF + r"\frac{\mathrm{EBIT}_i}{\mathrm{EV}_i},"
             r"\qquad \mathrm{EV}_i" + DEF +
             r"\mathrm{MC}_i+\mathrm{Debt}_i-\mathrm{Cash}_i",
    "mc": r"\mathrm{MC}_i" + DEF + r"S_i\times P_i",
    # ---------- Step 0 ----------
    "altman": r"Z_i\;=\;1.2\,\frac{\mathrm{WC}_i}{\mathrm{TA}_i}"
              r"+1.4\,\frac{\mathrm{RE}_i}{\mathrm{TA}_i}"
              r"+3.3\,\frac{\mathrm{EBIT}_i}{\mathrm{TA}_i}"
              r"+0.6\,\frac{\mathrm{MC}_i}{\mathrm{TL}_i}"
              r"+1.0\,\frac{\mathrm{Sales}_i}{\mathrm{TA}_i}",
    "liquidity": r"\mathrm{ADV}^{60}_i\;=\;\frac{1}{60}\sum_{t=1}^{60}P_{i,t}V_{i,t}"
                 r"\;\geq\;2\times10^{7}",
    # ---------- 自作式版 ----------
    "bespoke_moat": r"\mathrm{Moat}_i" + DEF +
                    r"\frac{1}{5}\left[\mathrm{pct}(\mathrm{GPA}_i)"
                    r"+\mathrm{pct}(\mathrm{OPM}_i)+\mathrm{pct}(\mathrm{ROA}_i)"
                    r"+\mathrm{pct}(\mathrm{OCFM}_i)+\mathrm{pct}(\mathrm{EQR}_i)\right]",
    "bespoke_change": r"\mathrm{Chg}_i" + DEF +
                      r"\frac{1}{6}\left[\mathrm{pct}(F_i)+\mathrm{pct}(\Delta\mathrm{ROA}_i)"
                      r"+\mathrm{pct}(\Delta\mathrm{GMAR}_i)+\mathrm{pct}(\Delta\mathrm{ATO}_i)"
                      r"+\mathrm{pct}(g^{\mathrm{S}}_i)+\mathrm{pct}(g^{\mathrm{OP}}_i)\right]",
    "bespoke_future": r"\mathrm{Fut}_i\;=\;\mathrm{pct}\left(0.30\,z(a_i)+0.25\,z(b_i)"
                      r"+0.20\,z(c_i)+0.15\,z(d_i)+0.10\,z(e_i)\right)",
    "bespoke_price": r"\mathrm{Pri}_i" + DEF +
                     r"\frac{1}{2}\left[\mathrm{pct}(\mathrm{EP}_i)"
                     r"+\mathrm{pct}(\mathrm{BM}_i)\right]",
    "growth": r"g^{\mathrm{S}}_i" + DEF +
              r"\frac{\mathrm{Sales}_i-\mathrm{Sales}^{-1}_i}{\left|\mathrm{Sales}^{-1}_i\right|},"
              r"\qquad \Delta\mathrm{ROA}_i" + DEF + r"\mathrm{ROA}_i-\mathrm{ROA}^{-1}_i",
}


def main() -> None:
    index: dict[str, dict[str, float]] = {}
    for name, latex in EQUATIONS.items():
        fig = plt.figure(figsize=(9, 1.2))
        fig.text(0.01, 0.5, f"${latex}$", fontsize=FONTSIZE, va="center")
        path = EQ_DIR / f"{name}.png"
        fig.savefig(path, dpi=DPI, transparent=True, bbox_inches="tight", pad_inches=0.04)
        plt.close(fig)

        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        disp_w = min(MAX_W_PX, w * 96 / DPI)
        index[name] = {"file": str(path), "w": round(disp_w), "h": round(disp_w * h / w)}
        print(f"{name:18s} {w}x{h}px → 表示 {index[name]['w']}x{index[name]['h']}")

    (OUT / "eq_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"\n{len(index)} 本の数式を書き出した")


if __name__ == "__main__":
    main()
