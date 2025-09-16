#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 KF5 Help Center API 验证本地抓取完整性：
1) 列出所有分类、分区（section）
2) 为每个分区分页获取文章ID
3) 对比本地 output_full/html 下是否存在对应 {article_id}_*.html 文件

输出：总数、缺失文章ID、冗余文章（本地有但 API 未返回）等。

依赖：
- 已配置 config/kf5_api.toml 或环境变量 KF5_BASE_URL / KF5_API_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests


def load_api_config() -> Tuple[str, str, Optional[str]]:
    """加载 API 配置（优先环境变量，其次 config/kf5_api.toml）。"""
    base = os.getenv("KF5_BASE_URL", "").strip()
    key = os.getenv("KF5_API_KEY", "").strip()
    email = os.getenv("KF5_API_EMAIL", "").strip() or None
    if not base or not key:
        cfg = Path("config/kf5_api.toml")
        if cfg.exists():
            try:
                import tomllib  # py311+
            except Exception:  # pragma: no cover
                import tomli as tomllib  # type: ignore
            data = tomllib.loads(cfg.read_text(encoding="utf-8"))
            hc = data.get("helpcenter", {})
            base = base or str(hc.get("base_url", "")).strip()
            key = key or str(hc.get("api_key", "")).strip()
            if not email:
                e = str(hc.get("email", "")).strip()
                email = e or None
    if not base or not key:
        raise SystemExit("KF5 API config missing. Set KF5_BASE_URL and KF5_API_KEY or edit config/kf5_api.toml")
    return base.rstrip("/"), key, email


class HC:
    def __init__(self, base_url: str, api_key: str, email: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.email = email
        self.s = requests.Session()
        self.s.headers.update({
            "Accept": "application/json",
            "User-Agent": "kintone-scraper-verify/0.1",
        })

        # KF5 不同站点 API 前缀可能不同，这里轮询尝试
        self.prefixes = [
            "api/v2/helpcenter",
            "api/v1/helpcenter",
            "apiv2/helpcenter",
            "apiv1/helpcenter",
            "hc/api/v2/helpcenter",
            "hc/api/v1/helpcenter",
        ]

    def _try_get(self, path: str, params: Dict = None) -> Dict:
        params = dict(params or {})
        last_exc = None
        # 多种鉴权风格（涵盖常见“邮箱+key”的站点）
        auth_variants = [
            # query 方式
            {"query": {"apikey": self.api_key}, "headers": {}, "auth": None},
            {"query": {"api_key": self.api_key}, "headers": {}, "auth": None},
            # header 方式
            {"query": {}, "headers": {"X-API-Key": self.api_key}, "auth": None},
            {"query": {}, "headers": {"apikey": self.api_key}, "auth": None},
            {"query": {}, "headers": {"Authorization": f"Token {self.api_key}"}, "auth": None},
            {"query": {}, "headers": {"Authorization": f"Bearer {self.api_key}"}, "auth": None},
        ]
        # 带邮箱的风格
        if self.email:
            auth_variants.extend([
                # Basic Auth: email:api_key
                {"query": {}, "headers": {}, "auth": (self.email, self.api_key)},
                # Basic Auth (KF5 常见风格): email/token:api_key
                {"query": {}, "headers": {}, "auth": (f"{self.email}/token", self.api_key)},
                # headers 搭配 email
                {"query": {}, "headers": {"X-API-Key": self.api_key, "X-User-Email": self.email}, "auth": None},
                {"query": {}, "headers": {"X-API-Key": self.api_key, "X-Email": self.email}, "auth": None},
                {"query": {"email": self.email, "apikey": self.api_key}, "headers": {}, "auth": None},
                {"query": {"user_email": self.email, "apikey": self.api_key}, "headers": {}, "auth": None},
            ])
        for pref in self.prefixes:
            url = f"{self.base_url}/{pref}/{path.lstrip('/')}"
            for auth in auth_variants:
                q = dict(params)
                q.update(auth["query"])  # may add apikey
                try:
                    r = self.s.get(url, params=q, headers=auth["headers"], auth=auth["auth"], timeout=20)
                    if r.status_code == 404:
                        # try next prefix
                        break
                    if r.status_code == 401:
                        # try next auth variant for same prefix
                        last_exc = requests.HTTPError("401 Unauthorized")
                        continue
                    r.raise_for_status()
                    return r.json()
                except Exception as e:
                    last_exc = e
                    continue
        if last_exc:
            raise last_exc
        raise RuntimeError("No API endpoint succeeded")

    def categories(self) -> List[Dict]:
        # 文档分类列表
        # 尝试新老风格：helpcenter/categories 或 简写 apiv2/categories.json
        try:
            data = self._try_get("categories")
            return data.get("categories", data.get("data", data))
        except Exception:
            pass
        data = self._try_get("../categories.json")  # maps to /apiv2/categories.json
        # 兼容不同返回结构
        return data.get("categories", data.get("data", data))

    def sections(self, category_id: int) -> List[Dict]:
        # 有些站点用 forums 表示分类；保持兼容
        try:
            data = self._try_get(f"categories/{category_id}/sections")
            return data.get("sections", data.get("data", data))
        except Exception:
            pass
        try:
            data = self._try_get(f"../categories/{category_id}/forums.json")
            return data.get("forums", data.get("data", data))
        except Exception:
            return []

    def articles(self, section_id: int, page: int = 1, per_page: int = 50) -> Dict:
        # 兼容两种结构：sections/{id}/articles 或 categories/{id}/posts.json / forums/{id}/posts.json
        # 先尝试 sections
        try:
            return self._try_get(f"sections/{section_id}/articles", params={"page": page, "per_page": per_page})
        except Exception:
            pass
        # 再尝试 categories/{id}/posts.json
        try:
            return self._try_get(f"../categories/{section_id}/posts.json", params={"page": page, "per_page": per_page})
        except Exception:
            # 最后尝试 forums/{id}/posts.json
            return self._try_get(f"../forums/{section_id}/posts.json", params={"page": page, "per_page": per_page})

    def list_all_posts(self, page: int = 1, per_page: int = 100) -> Tuple[List[Dict], bool]:
        """直接从 /apiv2/posts.json 列出文章，返回 (items, has_more)。"""
        data = self._try_get("../posts.json", params={"page": page, "per_page": per_page})
        items = data.get("posts") or data.get("data") or data.get("items") or []
        # KF5 常见上限 100；若无明确 has_more 字段，则用“满页即可能有下一页”的策略
        has_more = any(bool(data.get(k)) for k in ("has_more", "hasMore"))
        if not has_more:
            has_more = len(items) == per_page
        return items, has_more


def find_local_article_ids(html_root: Path) -> Set[str]:
    ids: Set[str] = set()
    pattern = re.compile(r"(\d+)_.*\.html$")
    for p in html_root.rglob("*.html"):
        m = pattern.search(p.name)
        if m:
            ids.add(m.group(1))
    return ids


def verify(root: Path, verbose: bool = False, base_url: str = "", api_key: str = "", email: Optional[str] = None) -> int:
    if base_url and api_key:
        base, key, mail = base_url, api_key, email
    else:
        base, key, mail = load_api_config()
        if email:
            mail = email
    api = HC(base, key, mail)

    html_root = root / "html"
    if not html_root.is_dir():
        raise SystemExit(f"HTML 目录不存在: {html_root}")

    local_ids = find_local_article_ids(html_root)

    total_api_articles = 0
    api_ids: Set[str] = set()

    # 优先直接拉取全部 posts（最简单）
    try:
        page = 1
        while True:
            items, more = api.list_all_posts(page=page, per_page=100)
            for it in items:
                aid = it.get("id") or it.get("post_id") or it.get("article_id") or it.get("_id")
                if aid:
                    api_ids.add(str(aid))
            total_api_articles += len(items)
            if not more or not items:
                break
            page += 1
    except Exception:
        # 回退：按分类/分区遍历
        cats = api.categories()
        for c in cats:
            cid = c.get("id") or c.get("category_id") or c.get("_id")
            if not cid:
                continue
            secs = api.sections(int(cid))
            for s in secs:
                sid = s.get("id") or s.get("section_id") or s.get("_id")
                if not sid:
                    continue
                page = 1
                while True:
                    data = api.articles(int(sid), page=page, per_page=100)
                    items = data.get("articles") or data.get("posts") or data.get("data") or []
                    if not isinstance(items, list) or not items:
                        break
                    for it in items:
                        aid = it.get("id") or it.get("post_id") or it.get("article_id") or it.get("_id")
                        if aid:
                            api_ids.add(str(aid))
                    total_api_articles += len(items)
                    has_more = False
                    for k in ("has_more", "hasMore"):
                        if k in data:
                            has_more = bool(data[k])
                    if not has_more and len(items) < 100:
                        break
                    page += 1

    missing = sorted(a for a in api_ids if a not in local_ids)
    extra = sorted(a for a in local_ids if a not in api_ids)

    print("=== 验证结果 ===")
    print(f"API 文章总数(去重): {len(api_ids)}  (累计分页计数: {total_api_articles})")
    print(f"本地文章总数   : {len(local_ids)}  (目录: {html_root})")
    print(f"缺失(应有未抓): {len(missing)}")
    if verbose and missing:
        print("  缺失ID:", ", ".join(missing[:200]))
        if len(missing) > 200:
            print("  ... 省略", len(missing) - 200, "个")
    print(f"冗余(API无此文): {len(extra)}")
    if verbose and extra:
        print("  冗余ID:", ", ".join(extra[:200]))
        if len(extra) > 200:
            print("  ... 省略", len(extra) - 200, "个")

    # 返回非零表示有不一致
    return 0 if not missing else 1


def main():
    ap = argparse.ArgumentParser(description="用KF5 API验证本地抓取完整性")
    ap.add_argument("output_root", type=Path, nargs="?", default=Path("output_full"), help="抓取输出根目录 (默认: output_full)")
    ap.add_argument("--verbose", "-v", action="store_true", help="打印缺失/冗余ID列表")
    ap.add_argument("--base", type=str, default="", help="KF5 基础域名，如 https://cybozudev.kf5.com")
    ap.add_argument("--key", type=str, default="", help="KF5 API Key（覆盖配置文件/环境变量）")
    ap.add_argument("--email", type=str, default="", help="KF5 账号邮箱（某些站点要求 email+key）")
    args = ap.parse_args()

    raise SystemExit(verify(args.output_root, verbose=args.verbose, base_url=args.base, api_key=args.key, email=args.email or None))


if __name__ == "__main__":
    main()
