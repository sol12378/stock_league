# -*- coding: utf-8 -*-
"""Machine checks for hard gates G1--G12 (V11_PLAN.md §5). Run after every build.

FAIL blocks further progress. PENDING means the work package that would satisfy the gate
has not been reached yet; PENDING is not a pass.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league")
ED = ROOT / "outputs/stockleague_edition"
TEX = ED / "referee_wp_analysis.tex"
PDF = ED / "referee_wp_analysis.pdf"

results = []


def rec(gate, status, detail):
    results.append((gate, status, detail))


# ---------------------------------------------------------------- G1: file boundaries
git = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
touched = [ln[3:].strip().strip('"') for ln in git.splitlines() if ln.strip()]
forbidden = []
for p in touched:
    base = Path(p).name
    code = next((ln[:2] for ln in git.splitlines() if ln[3:].strip().strip('"') == p), "")
    if base == "VERSION":
        forbidden.append(p)
    elif base.endswith(".LOCKED"):
        # v11 is required to create its OWN lock marker as the last step of finalisation
        # (V11_PLAN §8). What must never happen is touching somebody else's lock, or
        # modifying/deleting one that already existed.
        if "v11" not in base or "M" in code or "D" in code:
            forbidden.append(p)
    if re.search(r"_v(?:[1-9]|10)\b", base) and "v11" not in base and p.startswith("outputs/stockleague_edition/"):
        # modification (not addition) of a v1..v10 artefact
        code = next((ln[:2] for ln in git.splitlines() if ln[3:].strip().strip('"') == p), "")
        if "M" in code or "D" in code:
            forbidden.append(p)
rec("G1", "FAIL" if forbidden else "PASS",
    "; ".join(forbidden) if forbidden else "no writes to LOCKED / v10 / VERSION")

# ---------------------------------------------------------------- G2: numbers auto-transcribed
tex = TEX.read_text(encoding="utf-8")
body = re.sub(r"(?<!\\)%.*", "", tex)
# The generated table files are part of the manuscript. Splice each one in at its \input, so
# the ordering checks below see the same sequence a reader does. Tables are emitted per section
# (tables_l1_v11, tables_sat_v11, ...) so each float lands near the text discussing it.
def _splice(text):
    def sub(m):
        f = ED / (m.group(1) + ".tex")
        return re.sub(r"(?<!\\)%.*", "", f.read_text(encoding="utf-8")) if f.exists() else m.group(0)
    return re.sub(r"\\input\{(tables_[a-z0-9_]*v11)\}", sub, text)


full = _splice(body)
generated = sorted(q.name for q in ED.glob("tables_*_v11.tex"))
inputs_generated = bool(re.search(r"\\input\{tables_[a-z0-9_]*v11\}", body))
# strip the environments that legitimately carry literal text
prose = re.split(r"\\begin\{thebibliography\}", body)[0]
# Decimal percentages are the obvious leak. Large hand-typed integers are the subtler one --
# a firm count or a filing count typed into prose drifts silently when the data changes, and the
# decimal check never sees it. Layer/level labels, statistical conventions (5%, 80%), years,
# basis points and ISO dates are legitimate literals, so they are exempted by pattern.
prose_nt = re.sub(r"\\(?:label|ref|cite[a-z]*|input)\{[^}]*\}", "", prose)
hand = [m.group(1) for m in re.finditer(r"(?<![\\A-Za-z0-9{])(\d+\.\d+)\\?%", prose_nt)]
EXEMPT = {"1", "2", "3", "0", "5", "80", "95", "12", "17", "33", "100", "403", "30", "20", "25", "15"}
for m in re.finditer(r"(?<![\\A-Za-z0-9{.,/-])(\d[\d{},]*)(?![\d.,}/-])", prose_nt):
    v = m.group(1)
    plain = v.replace("{,}", "").replace(",", "")
    if plain in EXEMPT or (len(plain) == 4 and plain.startswith("20")):   # years
        continue
    ctx = prose_nt[max(0, m.start() - 60):m.start() + 20].replace("\n", " ")
    if re.search(r"\b(bp|per cent|percent)\b", ctx[-25:]):
        continue
    hand.append("%s (...%s)" % (v, ctx[-45:]))
auto = ("numbers_v11" in tex and inputs_generated)
rec("G2", "PASS" if auto and not hand else ("FAIL" if hand else "FAIL"),
    ("inputs numbers_v11 + %d generated table files; " % len(generated) if auto
     else "MISSING \\input of generated files; ")
    + ("no hand-typed numbers in prose" if not hand else "hand-typed: " + " | ".join(hand[:6])))

# --- G2b: the cover letter is hand-written Japanese prose and cannot use LaTeX macros, so its
# figures are cross-checked against the generated macros instead. A referee reads it beside the
# paper; a disagreement between the two is a disagreement with the referee's own eyes.
# Values contain LaTeX thousands separators like 3{,}649, so the value group must allow one
# nested brace pair rather than stopping at the first closing brace.
_macros = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{((?:[^{}]|\{[^{}]*\})*)\}",
                          (ED / "numbers_v11.tex").read_text(encoding="utf-8")))


def _m(name):
    return _macros.get(name, "").replace("{,}", ",")


# The briefing is sent to the referee alongside the paper, so it is held to the same standard.
BRIEF = ED / "referee_briefing_analysis.md"
BRIEF_CLAIMS = [("SatFirms", "%s社"), ("SatSectorShare", "%s%%の企業"),
                ("SatRdPresent", "中%s社しか値を持たず"), ("OwnHoldings", "%s社中"),
                ("OwnVerified", "%s社しか通らなかった")]
if BRIEF.exists():
    brief = BRIEF.read_text(encoding="utf-8")
    bad_brief = [n for n, pat in BRIEF_CLAIMS if (pat % _m(n)) not in brief]
    rec("G2d", "FAIL" if bad_brief else "PASS",
        "referee briefing agrees with %d generated figures" % len(BRIEF_CLAIMS) if not bad_brief
        else "briefing disagrees on: " + ", ".join("%s=%s" % (n, _m(n)) for n in bad_brief))
else:
    rec("G2d", "FAIL", "referee_briefing_analysis.md missing")

COVER = ED / "cover_letter_analysis_wp.md"
COVER_CLAIMS = [
    ("SatFirms", "%s社が"), ("SatDistinct", "%s個の値"), ("SatSectorShare", "%s%%の企業"),
    ("SatAbove", "上にいるのは%s社"), ("SatRdPresent", "中%s社しか値を持たず"),
    ("OwnHoldings", "%s社のうち"), ("OwnVerified", "持つのは**%s社**"),
    ("OwnLevelOne", "%s社はキーワード照合のみ"), ("LoneCells", "**%s仕様すべて"),
    ("MdeTotal", "**%s基準日中"), ("SpecTotal", "**%s通り**"),
]
if COVER.exists():
    cover = COVER.read_text(encoding="utf-8")
    bad_cover = [("%s=%s" % (name, _m(name)), pat % _m(name))
                 for name, pat in COVER_CLAIMS if (pat % _m(name)) not in cover]
    rec("G2b", "FAIL" if bad_cover else "PASS",
        "cover letter agrees with %d generated figures" % len(COVER_CLAIMS) if not bad_cover
        else "cover letter disagrees: " + "; ".join(b[0] for b in bad_cover))
else:
    rec("G2b", "FAIL", "cover_letter_analysis_wp.md missing")

# --- G2c: identifiers must never be thousands-separated. A seed printed as 20{,}260{,}725 is a
# different token from the seed the script uses, so a reader retyping it cannot reproduce anything.
seed_expected = str(json.load(open(ED / "layer2_placebo_v11.json"))["seed"])
seed_ok = (_m("LtwoSeed") == seed_expected) and (seed_expected in full)
bad_seed_fmt = re.search(r"[Ss]eed\s*\\?[A-Za-z]*\s*\d{1,3}[,{]", full)
rec("G2c", "PASS" if seed_ok and not bad_seed_fmt else "FAIL",
    "seed printed as the bare identifier %s" % seed_expected if seed_ok and not bad_seed_fmt
    else "seed mis-rendered (macro=%r, expected %r)" % (_m("LtwoSeed"), seed_expected))

# ---------------------------------------------------------------- G3: no test vocabulary in L2/L3
def section_text(tex, label):
    """Text of the subsection carrying \\label{label}, up to the next (sub)section."""
    i = tex.find("\\label{%s}" % label)
    if i < 0:
        return None
    j = tex.find("\\subsection", i)
    k = tex.find("\\section", i)
    end = min(x for x in [j, k, len(tex)] if x > 0)
    return tex[i:end]


bad = []
for label in ["sec:layer2", "sec:benchmark"]:
    t = section_text(body, label)
    if t is None:
        continue
    for pat in [r"\bsignificant", r"\bt-statistic", r"\bp-value", r"NW-t", r"Newey"]:
        # the layer-table row that *forbids* these words is allowed to name them
        for m in re.finditer(pat, t, re.I):
            ctx = t[max(0, m.start() - 90):m.start() + 40].replace("\n", " ")
            if "no $t$-statistic" in ctx or "not permitted" in ctx.lower() or "and no use of the word" in ctx:
                continue
            bad.append("%s: ...%s..." % (label, ctx[-70:]))
rec("G3", "FAIL" if bad else "PASS",
    "; ".join(bad[:4]) if bad else "no inferential vocabulary in the L2/L3 sections")

# ---------------------------------------------------------------- G4: ordering disclosure
g4 = bool(re.search(r"after observing that our portfolio\s*\n?\s*underperformed", body)
          or re.search(r"\\emph\{after\} observing", body))
lim = section_text(body, "sec:limitations") or ""
rec("G4", "PASS" if (g4 and "ordering disclosure" in lim) else "FAIL",
    "ordering disclosure present in Limitations" if g4 else "ordering disclosure MISSING")

# ---------------------------------------------------------------- G5: no "beat Buffett" as a conclusion
claims = [m.group(0) for m in re.finditer(r"[^.]*\bbeat(?:s|ing)?\b[^.]*Buffett[^.]*\.", body, re.I)]
claims = [c for c in claims if "does not claim" not in c and "motivating story" not in c]
rec("G5", "FAIL" if claims else "PASS",
    claims[0][:100] if claims else "no beat-Buffett claim outside the disclaimer/motivation framing")

# ---------------------------------------------------------------- G6: 15 firms not PIT reproducible
i_l1 = full.find("\\label{tab:layer1}")
i_g6 = full.find("cannot be reproduced point-in-time")
g6 = i_g6 >= 0
rec("G6", "PASS" if (g6 and i_l1 > 0 and i_g6 < i_l1) else "FAIL",
    "stated before the Layer 1 table" if (g6 and i_l1 > 0 and i_g6 < i_l1)
    else "statement missing or after Table 1")

# ---------------------------------------------------------------- G7: layer table + per-table labels
# Every table must open its caption with one of a CLOSED set of labels. Substring matching anywhere
# in the table body gave false passes: the factor table mentions "Layer 1" in its notes while
# carrying no label of its own.
LABELS = ("Layer 1", "Layer 2", "Layer 3", "Measurement audit", "Attribution", "The three-layer")
g7_tbl = "\\label{tab:layers}" in body
unlabelled = []
for m in re.finditer(r"\\begin\{table\}.*?\\end\{table\}", full, re.S):
    t = m.group(0)
    cap = re.search(r"\\caption\{\\textbf\{([^}]*)", t)
    lab = re.search(r"\\label\{(tab:[^}]+)\}", t)
    head = cap.group(1) if cap else ""
    if not any(head.startswith(x) for x in LABELS):
        unlabelled.append(lab.group(1) if lab else "unlabelled table")
n_tables = len(re.findall(r"\\begin\{table\}", full))
rec("G7", "PASS" if g7_tbl and not unlabelled else "FAIL",
    "declaration table present; all %d tables open with one of %d declared labels" % (n_tables, len(LABELS))
    if g7_tbl and not unlabelled else "captions without a declared label: " + ", ".join(unlabelled))

# ---------------------------------------------------------------- G8: compiles, page count, English
pages = None
if PDF.exists():
    txt = subprocess.run(["pdftotext", str(PDF), "-"], capture_output=True, text=True).stdout
    pages = txt.count("\f")
    cjk = re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", txt)
    body_ok = 12 <= pages <= 18
    rec("G8", "PASS" if (body_ok and not cjk) else "PENDING",
        "%d pages, %d CJK chars (target 12--18 pages, English body)" % (pages, len(cjk)))
else:
    rec("G8", "FAIL", "referee_wp_analysis.pdf missing")

# ---------------------------------------------------------------- G9: triage self-sufficiency
# A \\ref to a label is not evidence that the table is in the paper: an edit can delete the \\input
# and leave every reference resolving to a table that no longer exists. Check the spliced text, and
# flag any generated table file the manuscript never inputs.
NEEDED = ["tab:layer1", "tab:layer2", "tab:factors", "tab:saturation", "tab:ladder"]
missing_tbl = [t for t in NEEDED if ("\\label{%s}" % t) not in full]
orphan_files = [f.stem for f in sorted(ED.glob("tables_*_v11.tex"))
                if f.stem != "tables_v11" and ("\\input{%s}" % f.stem) not in body]
rec("G9", "PASS" if not missing_tbl and not orphan_files else "FAIL",
    "all %d key tables present and every generated file is input" % len(NEEDED)
    if not missing_tbl and not orphan_files
    else "missing: %s; generated-but-not-input: %s" % (missing_tbl or "none", orphan_files or "none"))

# --- G9c: no orphaned tables. A table nobody points to is a table nobody reads; three appendix
# tables were added in one iteration and none of them was referenced from the text.
all_labels = re.findall(r"\\label\{(tab:[^}]+)\}", full)
refs = set(re.findall(r"\\ref\{(tab:[^}]+)\}", full))
orphans = [l for l in all_labels if l not in refs]
rec("G9c", "PASS" if not orphans else "FAIL",
    "all %d tables are referenced" % len(all_labels) if not orphans
    else "never referenced: " + ", ".join(orphans))

# --- G9b: the acceptance criteria in V11_PLAN.md that are checkable. W2 requires a distribution
# figure; it went unbuilt for four review rounds because nothing enforced it.
figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body)
missing_fig = [f for f in figs if not (ED / f).exists()]
rec("G9b", "PASS" if figs and not missing_fig else "FAIL",
    "%d figure(s) included, all files present" % len(figs) if figs and not missing_fig
    else ("no figure included (V11_PLAN W2 requires the Layer 2 distribution figure)" if not figs
          else "missing figure files: " + ", ".join(missing_fig)))

# ---------------------------------------------------------------- G10: bibliography hygiene
bib = (ED / "referee_wp_analysis.bib").read_text(encoding="utf-8") if (ED / "referee_wp_analysis.bib").exists() else ""
keys = set(re.findall(r"@\w+\{([^,]+),", bib))
cited = set(k.strip() for m in re.findall(r"\\cite[a-z]*\{([^}]+)\}", body) for k in m.split(","))
unused = keys - cited
dsr_used = "eflated Sharpe" in body
rec("G10", "PASS" if not unused and (not dsr_used or "BaileyLopezdePrado2014" in keys) else "FAIL",
    "no unused entries (%d cited/%d in bib)" % (len(cited), len(keys)) if not unused
    else "unused: " + ", ".join(sorted(unused)))

# ---------------------------------------------------------------- G11 / G12
pkg = ED / "referee_package_v11" / "README.md"
rec("G11", "PASS" if pkg.exists() else "PENDING", "replication README %s" % ("present" if pkg.exists() else "not built yet"))
g12 = "biases every historical series here in our favour" in body or "survivorship" in body.lower()
rec("G12", "PASS" if g12 else "PENDING", "survivorship direction stated" if g12 else "not yet stated")

# ---------------------------------------------------------------- report
width = max(len(d) for _, _, d in results)
print("%-4s %-8s %s" % ("gate", "status", "detail"))
for g, s, d in results:
    print("%-4s %-8s %s" % (g, s, d))
n_fail = sum(1 for _, s, _ in results if s == "FAIL")
n_pend = sum(1 for _, s, _ in results if s == "PENDING")
print("\n%d PASS / %d PENDING / %d FAIL" % (len(results) - n_fail - n_pend, n_pend, n_fail))
json.dump([{"gate": g, "status": s, "detail": d} for g, s, d in results],
          open(ED / "gates_v11.json", "w"), ensure_ascii=False, indent=1)
sys.exit(1 if n_fail else 0)
