from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import requests


CONFIG_FILE = Path("config/kf5_api.toml")


def _load_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {"helpcenter": {}}
    if CONFIG_FILE.exists():
        try:
            import tomllib  # Python 3.11+
        except Exception:  # pragma: no cover
            import tomli as tomllib  # type: ignore
        data = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        cfg.update(data)
    # Allow env overrides
    if os.getenv("KF5_API_KEY"):
        cfg.setdefault("helpcenter", {})["api_key"] = os.environ["KF5_API_KEY"]
    if os.getenv("KF5_BASE_URL"):
        cfg.setdefault("helpcenter", {})["base_url"] = os.environ["KF5_BASE_URL"]
    if os.getenv("KF5_API_EMAIL"):
        cfg.setdefault("helpcenter", {})["email"] = os.environ["KF5_API_EMAIL"]
    return cfg


@dataclass
class KF5Config:
    base_url: str
    api_key: str
    email: Optional[str] = None

    @classmethod
    def load(cls) -> "KF5Config":
        cfg = _load_config().get("helpcenter", {})
        base = cfg.get("base_url", "").rstrip("/")
        key = cfg.get("api_key", "")
        email = cfg.get("email") or None
        if not base or not key:
            raise RuntimeError("KF5 API config missing: base_url/api_key")
        return cls(base_url=base, api_key=key, email=email)


class KF5HelpCenterClient:
    """Lightweight KF5 Help Center API client.

    Note: KF5 API auth can vary by deployment. Some use header, some query token.
    This client supports both and can be adjusted once the exact scheme is confirmed.
    """

    def __init__(self, config: Optional[KF5Config] = None):
        self.config = config or KF5Config.load()
        self.session = requests.Session()
        # Common headers; adjust if API requires a specific header name
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "kintone-scraper/0.1",
        })

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self.config.base_url}/{path}"

    def _auth_params(self) -> Dict[str, str]:
        # If API requires query token (fallback)
        return {"apikey": self.config.api_key}

    def _auth_headers(self) -> Dict[str, str]:
        # If API requires header token (alternative)
        return {"X-API-Key": self.config.api_key}

    def _request_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Try multiple API prefixes and auth variants until one succeeds."""
        params = dict(params or {})
        prefixes = [
            # apiv2 simplified endpoints (recommended)
            "apiv2",
            # legacy helpcenter endpoints
            "api/v2/helpcenter",
            "api/v1/helpcenter",
            "api/v2/help_center",
            "api/v1/help_center",
            "hc/api/v2/helpcenter",
            "hc/api/v1/helpcenter",
        ]
        last_exc: Optional[Exception] = None
        # auth variants
        auth_variants: List[Tuple[Dict[str, str], Dict[str, str], Optional[Tuple[str, str]]]] = [
            ({"apikey": self.config.api_key}, {}, None),
            ({"api_key": self.config.api_key}, {}, None),
            ({}, {"X-API-Key": self.config.api_key}, None),
            ({}, {"apikey": self.config.api_key}, None),
            ({}, {"Authorization": f"Token {self.config.api_key}"}, None),
            ({}, {"Authorization": f"Bearer {self.config.api_key}"}, None),
        ]
        if self.config.email:
            auth_variants.extend([
                ({}, {}, (self.config.email, self.config.api_key)),
                ({}, {}, (f"{self.config.email}/token", self.config.api_key)),
                ({"email": self.config.email, "apikey": self.config.api_key}, {}, None),
                ({"user_email": self.config.email, "apikey": self.config.api_key}, {}, None),
                ({}, {"X-API-Key": self.config.api_key, "X-User-Email": self.config.email}, None),
            ])

        for pref in prefixes:
            url = self._url(f"{pref}/{path.lstrip('/')}")
            for q, h, ba in auth_variants:
                try:
                    p = dict(params)
                    p.update(q)
                    r = self.session.get(url, params=p, headers=h, auth=ba, timeout=30)
                    if r.status_code == 404:
                        break
                    if r.status_code == 401:
                        last_exc = requests.HTTPError("401 Unauthorized")
                        continue
                    r.raise_for_status()
                    return r.json()
                except Exception as e:
                    last_exc = e
                    continue
        if last_exc:
            raise last_exc
        raise RuntimeError("KF5 API: no endpoint succeeded")

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request_json(path, params)

    # High-level endpoints (paths to be verified against docs)
    def list_categories(self) -> Dict[str, Any]:
        # KF5 API: GET /apiv2/categories.json - 获取文档分区列表
        return self.get("categories.json")

    def list_forums(self, category_id: Optional[int] = None) -> Dict[str, Any]:
        # KF5 API: GET /apiv2/forums.json - 获取文档分类列表
        params = {}
        if category_id:
            params['category_id'] = category_id
        return self.get("forums.json", params=params)
    
    def list_forums_by_category(self, category_id: int) -> Dict[str, Any]:
        # KF5 API: GET /apiv2/categories/{id}/forums.json - 获取指定分区下的分类列表
        return self.get(f"categories/{category_id}/forums.json")

    def get_forum(self, forum_id: int) -> Dict[str, Any]:
        # KF5 API: GET /apiv2/forums/{id}.json - 查看文档分类详情
        return self.get(f"forums/{forum_id}.json")

    def list_sections(self, category_id: int) -> Dict[str, Any]:
        # Example: /api/v1/helpcenter/categories/{id}/sections
        return self.get(f"categories/{category_id}/sections")

    def list_articles(self, section_id: int, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        # Example: /api/v1/helpcenter/sections/{id}/articles
        return self.get(f"sections/{section_id}/articles", params={"page": page, "per_page": per_page})

    def get_article(self, article_id: int) -> Dict[str, Any]:
        # Example: /api/v1/helpcenter/articles/{id}
        return self.get(f"articles/{article_id}")

    def list_article_attachments(self, article_id: int) -> Dict[str, Any]:
        # Example: /api/v1/helpcenter/articles/{id}/attachments
        return self.get(f"articles/{article_id}/attachments")

    # apiv2 list all posts
    def list_all_posts(self, page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        # apiv2/posts.json （不要使用 ../ 前缀，交由前缀拼装）
        return self.get("posts.json", params={"page": page, "per_page": per_page})

    def get_post(self, post_id: int) -> Dict[str, Any]:
        # KF5 API: GET /apiv2/posts/{id}.json - 查看文档详情
        return self.get(f"posts/{post_id}.json")
    
    def list_posts_by_forum(self, forum_id: int, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        # KF5 API: GET /apiv2/posts.json?forum_id={forum_id} - 获取指定分类的文章列表
        return self.get("posts.json", params={"forum_id": forum_id, "page": page, "per_page": per_page})

    def build_category_mapping(self) -> Dict[int, Dict[str, Any]]:
        """构建forum_id到完整分类路径的映射，按照KF5 API层级结构"""
        try:
            # 1. 获取所有分区 (categories)
            print("🔍 获取所有分区...")
            categories_resp = self.list_categories()
            categories = categories_resp.get('categories', [])
            print(f"📂 找到 {len(categories)} 个分区")
            
            # 构建forum_id到完整路径的映射
            forum_mapping = {}
            
            # 2. 遍历每个分区，获取其下的分类 (forums)
            for category in categories:
                category_id = category['id']
                category_name = category['title']
                print(f"📂 处理分区: {category_name} (ID: {category_id})")
                
                try:
                    # 使用标准API获取该分区下的分类
                    forums_resp = self.list_forums_by_category(category_id)
                    forums = forums_resp.get('forums', [])
                    print(f"  📁 找到 {len(forums)} 个分类")
                    
                    for forum in forums:
                        forum_id = forum['id']
                        forum_name = forum['title']
                        full_path = f"{category_name}/{forum_name}"
                        
                        forum_mapping[forum_id] = {
                            'forum_name': forum_name,
                            'category_name': category_name,
                            'category_id': category_id,
                            'full_path': full_path
                        }
                        print(f"    📄 {forum_name} -> {full_path}")
                        
                except Exception as e:
                    print(f"  ⚠️  获取分区 {category_name} 下的分类失败: {e}")
                    continue
            
            print(f"✅ 构建完成，共 {len(forum_mapping)} 个分类映射")
            return forum_mapping
            
        except Exception as e:
            print(f"⚠️  构建分类映射失败: {e}")
            return {}


__all__ = ["KF5Config", "KF5HelpCenterClient"]
