#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

from kintone_scraper.kf5_api import KF5HelpCenterClient


def enrich(html_root: Path) -> None:
    client = KF5HelpCenterClient()
    html_files = list(html_root.rglob("*.html"))
    total = 0
    ok = 0
    for fp in html_files:
        m = re.match(r"^(\d+)_", fp.name)
        if not m:
            continue
        total += 1
        aid = int(m.group(1))
        meta = {}
        try:
            meta["article"] = client.get_article(aid)
        except Exception as e:
            meta["article_error"] = str(e)
        try:
            meta["attachments"] = client.list_article_attachments(aid)
        except Exception as e:
            meta["attachments_error"] = str(e)
        sidecar = fp.with_suffix(".api.json")
        sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        ok += 1
    print(f"API enrich: wrote sidecars for {ok}/{total} html files under {html_root}")


def main(argv):
    if not argv:
        print("Usage: enrich_with_api.py <html_dir>")
        sys.exit(1)
    html_dir = Path(argv[0])
    if not html_dir.exists():
        print(f"HTML dir not found: {html_dir}")
        sys.exit(1)
    enrich(html_dir)


if __name__ == "__main__":
    main(sys.argv[1:])

