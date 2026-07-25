# -*- coding: utf-8 -*-
"""PDFから各章の開始ページを検出して tocmap.json を書く(2パスビルドのパス間処理)。"""
import json
import subprocess
import sys
from pathlib import Path

ED = Path(__file__).parent.parent
VER = sys.argv[1] if len(sys.argv) > 1 else ((ED / "VERSION").read_text().strip() if (ED / "VERSION").exists() else "dev")
pdf = ED / f"beyond_buffett_stockleague_{VER}.pdf"
items = ["要旨", "Ⅰ．背景・投資テーマ決定", "Ⅱ．スクリーニング ― 守・破・離",
         "Ⅲ．ポートフォリオの決定・銘柄紹介・パフォーマンス", "Ⅳ．インタビュー・アンケート",
         "Ⅴ．日経ＳＴＯＣＫリーグを通じて学んだこと", "参考文献", "用語の手引き"]

npages = 0
info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
for line in info.splitlines():
    if line.startswith("Pages:"):
        npages = int(line.split()[-1])
pages = []
for i in range(1, npages + 1):
    r = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(pdf), "-"],
                       capture_output=True, text=True)
    pages.append(r.stdout.replace(" ", "").replace("　", ""))

keys = [it.replace(" ", "").replace("　", "") for it in items]
toc_pages = {i + 1 for i, t in enumerate(pages) if sum(1 for k in keys if k in t) >= 4}
out = {}
for it, key in zip(items, keys):
    hits = [i + 1 for i, t in enumerate(pages) if key in t]
    hits_non_toc = [h for h in hits if h not in toc_pages]
    out[it] = hits_non_toc[0] if hits_non_toc else (hits[0] if hits else "")
json.dump(out, open(ED / f"tocmap_{VER}.json", "w"), ensure_ascii=False, indent=1)
print("pages:", npages, "| tocmap:", out)
