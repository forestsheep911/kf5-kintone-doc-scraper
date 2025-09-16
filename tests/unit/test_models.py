"""测试数据模型"""

import pytest
from datetime import datetime

from kintone_scraper.models import Article, Section, Category, ScrapingResult


class TestArticle:
    """测试Article模型"""
    
    def test_article_creation(self):
        """测试创建文章对象"""
        article = Article(
            url="https://example.com/article/123",
            title="测试文章",
            content="这是测试内容" * 100
        )
        
        assert article.url == "https://example.com/article/123"
        assert article.title == "测试文章"
        assert article.content_length == len("这是测试内容" * 100)
        assert article.scraped_at is not None
    
    def test_article_to_dict(self):
        """测试转换为字典"""
        article = Article(
            url="https://example.com/article/123",
            title="测试文章",
            content="测试内容"
        )
        
        data = article.to_dict()
        
        assert data['title'] == "测试文章"
        assert data['url'] == "https://example.com/article/123"
        assert data['content'] == "测试内容"
        assert 'scraped_at' in data
    
    def test_article_from_dict(self):
        """测试从字典创建对象"""
        data = {
            'url': 'https://example.com/article/123',
            'title': '测试文章',
            'content': '测试内容',
            'category': 'API文档',
            'scraped_at': '2024-01-01T00:00:00'
        }
        
        article = Article.from_dict(data)
        
        assert article.url == data['url']
        assert article.title == data['title']
        assert article.content == data['content']
        assert article.category == data['category']


class TestSection:
    """测试Section模型"""
    
    def test_section_creation(self):
        """测试创建section对象"""
        articles = [
            "https://example.com/article/1",
            "https://example.com/article/2"
        ]
        
        section = Section(
            url="https://example.com/section/1",
            title="测试Section",
            articles=articles
        )
        
        assert section.url == "https://example.com/section/1"
        assert section.title == "测试Section"
        assert section.article_count == 2
        assert section.articles == articles
    
    def test_section_serialization(self):
        """测试序列化和反序列化"""
        section = Section(
            url="https://example.com/section/1",
            title="测试Section",
            articles=["https://example.com/article/1"]
        )
        
        data = section.to_dict()
        new_section = Section.from_dict(data)
        
        assert new_section.url == section.url
        assert new_section.title == section.title
        assert new_section.articles == section.articles


class TestCategory:
    """测试Category模型"""
    
    def test_category_creation(self):
        """测试创建分类对象"""
        category = Category(
            name="API文档",
            path="API文档"
        )
        
        assert category.name == "API文档"
        assert category.path == "API文档"
        assert category.total_articles == 0
        assert len(category.sections) == 0
    
    def test_add_section(self):
        """测试添加section"""
        category = Category(name="API文档", path="API文档")
        
        section = Section(
            url="https://example.com/section/1",
            title="REST API"
        )
        section.article_count = 5  # 手动设置
        
        category.add_section(section)
        
        assert len(category.sections) == 1
        assert category.total_articles == 5
    
    def test_category_serialization(self):
        """测试分类序列化"""
        category = Category(name="API文档", path="API文档")
        
        section = Section(
            url="https://example.com/section/1",
            title="REST API"
        )
        section.article_count = 3  # 手动设置
        category.add_section(section)
        
        data = category.to_dict()
        new_category = Category.from_dict(data)
        
        assert new_category.name == category.name
        assert new_category.total_articles == category.total_articles
        assert len(new_category.sections) == len(category.sections)


class TestScrapingResult:
    """测试抓取结果模型"""
    
    def test_scraping_result_creation(self):
        """测试创建抓取结果"""
        result = ScrapingResult()
        
        assert result.total_articles == 0
        assert result.successful_articles == 0
        assert result.failed_articles == 0
        assert result.start_time is not None
    
    def test_add_article(self):
        """测试添加文章"""
        result = ScrapingResult()
        
        article = Article(
            url="https://example.com/article/1",
            title="测试文章"
        )
        
        result.add_article(article, success=True)
        
        assert result.successful_articles == 1
        assert result.failed_articles == 0
        assert len(result.articles) == 1
    
    def test_success_rate(self):
        """测试成功率计算"""
        result = ScrapingResult()
        result.total_articles = 10
        result.successful_articles = 8
        result.failed_articles = 2
        
        assert result.get_success_rate() == 0.8
    
    def test_mark_completed(self):
        """测试标记完成"""
        result = ScrapingResult()
        result.mark_completed()
        
        assert result.end_time is not None
        assert result.duration is not None
