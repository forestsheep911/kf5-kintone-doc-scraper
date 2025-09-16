#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import requests


BASE_DOMAIN = os.environ.get("KF5_BASE_URL", "https://cybozudev.kf5.com").rstrip("/")
API_KEY = os.environ.get("KF5_API_KEY", "d8b210560a4d1a73705bcb9130924e")


def try_get(url: str, headers: Dict[str, str]) -> Tuple[int, str, Dict]:
    try:
        r = requests.get(url, headers=headers, timeout=20)
        ct = r.headers.get('Content-Type', '')
        data = None
        if 'application/json' in ct:
            try:
                data = r.json()
            except Exception:
                data = None
        return r.status_code, ct, data if isinstance(data, dict) else {"raw": (data if data is not None else r.text[:500])}
    except Exception as e:
        return 0, 'error', {"error": str(e)}


def main():
    # Choose one known article id from existing output filenames
    article_id = "1314677"
    candidates = [
        f"{BASE_DOMAIN}/api/v1/helpcenter/articles/{article_id}",
        f"{BASE_DOMAIN}/api/v1/helpcenter/article/{article_id}",
        f"{BASE_DOMAIN}/api/v1/help_center/articles/{article_id}",
        f"{BASE_DOMAIN}/api/v1/kb/articles/{article_id}",
        f"{BASE_DOMAIN}/api/v2/helpcenter/articles/{article_id}",
    ]

    headers_list = [
        {},
        {"X-API-Key": API_KEY},
        {"X-Auth-Token": API_KEY},
        {"Authorization": f"Bearer {API_KEY}"},
    ]

    print(f"Base: {BASE_DOMAIN}\nTrying {len(candidates)} endpoints × {len(headers_list)} auth headers...\n")
    for url in candidates:
        print(f"==> {url}")
        for h in headers_list:
            status, ct, data = try_get(url + f"?apikey={API_KEY}", headers=h)
            tag = ", ".join([f"{k}" for k in h.keys()]) or "-"
            print(f"  headers[{tag:12}] -> {status} {ct}")
            if isinstance(data, dict) and any(k in data for k in ("id", "article", "data")):
                snippet = json.dumps(data, ensure_ascii=False)[:400]
                print(f"    payload: {snippet}...")
                return
        print()

    print("No JSON payload found. Consider adjusting endpoint patterns.")


if __name__ == '__main__':
    main()

