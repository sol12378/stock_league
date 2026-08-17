from __future__ import annotations

import io
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from lxml import etree


OUTER = Path("../data/raw/edinet/xbrl.zip")


def local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag.split(":")[-1]


def main(doc_id: str) -> None:
    patterns = re.compile(
        r"Revenue|NetSales|OperatingIncome|OperatingProfit|MajorShare|Shareholding|"
        r"LargeShare|Name.*Shareholder|Listing|Listed|StockExchange|CompanyHistory|History|Officer|Director|President",
        re.I,
    )
    with zipfile.ZipFile(OUTER) as outer:
        raw = outer.read(f"xbrl/{doc_id}.zip")
    with zipfile.ZipFile(io.BytesIO(raw)) as inner:
        print("members", len(inner.namelist()))
        parser = etree.XMLParser(recover=True, huge_tree=True)
        seen: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for member in inner.namelist():
            if not member.lower().endswith((".xbrl", ".xml", ".htm", ".html", ".xhtml")):
                continue
            try:
                root = etree.fromstring(inner.read(member), parser=parser)
            except Exception:
                continue
            for elem in root.iter():
                name = local_name(str(elem.tag))
                if not patterns.search(name):
                    continue
                max_len = 5000 if name == "CompanyHistoryTextBlock" else 160
                text = " ".join("".join(elem.itertext()).split())[:max_len]
                context = elem.attrib.get("contextRef") or elem.attrib.get("contextref") or ""
                if (context, text) not in seen[name]:
                    seen[name].add((context, text))
                    print(name, "|", context, "|", text)


if __name__ == "__main__":
    main(sys.argv[1])
