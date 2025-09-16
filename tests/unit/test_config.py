"""测试配置模块"""

import pytest
from kintone_scraper.config import (
    BASE_URL, DEFAULT_HEADERS, SELECTORS, CATEGORY_MAPPING, MAIN_CATEGORIES,
    get_safe_filename, get_category_path
)


class TestConfig:
    """测试配置常量"""
    
    def test_base_url(self):
        """测试基础URL配置"""
        assert BASE_URL == "https://cybozudev.kf5.com/hc/"
        assert BASE_URL.endswith("/")
    
    def test_default_headers(self):
        """测试默认请求头"""
        assert 'User-Agent' in DEFAULT_HEADERS
        assert 'Accept' in DEFAULT_HEADERS
        assert 'Accept-Language' in DEFAULT_HEADERS
        
        # 验证User-Agent不为空
        assert len(DEFAULT_HEADERS['User-Agent']) > 0
    
    def test_selectors(self):
        """测试选择器配置"""
        required_selectors = ['section_links', 'article_links', 'title', 'content', 'breadcrumb']
        
        for selector in required_selectors:
            assert selector in SELECTORS
            assert SELECTORS[selector] is not None
    
    def test_category_mapping(self):
        """测试分类映射"""
        assert isinstance(CATEGORY_MAPPING, dict)
        assert len(CATEGORY_MAPPING) > 0
        
        # 检查一些关键分类
        assert 'kintone REST API' in CATEGORY_MAPPING
        assert 'kintone JavaScript API' in CATEGORY_MAPPING
    
    def test_main_categories(self):
        """测试主要分类结构"""
        assert isinstance(MAIN_CATEGORIES, dict)
        assert len(MAIN_CATEGORIES) > 0
        
        # 检查关键主分类
        assert 'API文档' in MAIN_CATEGORIES
        assert '插件' in MAIN_CATEGORIES
        assert '新手教程' in MAIN_CATEGORIES
        
        # 检查子分类结构
        api_docs = MAIN_CATEGORIES['API文档']
        assert isinstance(api_docs, list)
        assert 'kintone REST API' in api_docs


class TestConfigFunctions:
    """测试配置函数"""
    
    def test_get_safe_filename(self):
        """测试安全文件名生成"""
        # 测试特殊字符替换
        assert get_safe_filename("文件/名称") == "文件_名称"
        assert get_safe_filename("test:file") == "test：file"
        assert get_safe_filename("file*name") == "file＊name"
        assert get_safe_filename("file<>name") == "file＜＞name"
        
        # 测试长度限制
        long_name = "a" * 150
        result = get_safe_filename(long_name, max_length=50)
        assert len(result) <= 50
        assert result.endswith("...")
        
        # 测试空白处理
        assert get_safe_filename("  filename  ") == "filename"
        assert get_safe_filename("filename.") == "filename"
    
    def test_get_category_path(self):
        """测试分类路径获取"""
        # 测试直接匹配
        path = get_category_path("kintone REST API")
        assert path == "API文档/kintone REST API"
        
        path = get_category_path("插件开发")
        assert path == "插件/插件开发"
        
        # 测试模糊匹配
        path = get_category_path("REST API基础")
        assert "API文档" in path
        
        # 测试未知分类
        path = get_category_path("未知分类")
        assert path.startswith("其他/")
    
    def test_get_category_path_edge_cases(self):
        """测试分类路径边界情况"""
        # 测试空字符串
        path = get_category_path("")
        assert path == "其他/未知"
        
        # 测试None
        path = get_category_path(None)
        assert path == "其他/未知"
        
        # 测试特殊字符
        path = get_category_path("API/文档")
        assert isinstance(path, str)
        assert len(path) > 0
