"""测试抓取器功能"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup

from kintone_scraper.scraper import KintoneScraper
from kintone_scraper.models import Article, Section


@pytest.fixture
def scraper():
    """创建测试用的抓取器实例"""
    return KintoneScraper(output_dir=Path("test_output"))


@pytest.fixture
def mock_html():
    """模拟HTML内容"""
    return """
    <html>
        <head><title>测试页面</title></head>
        <body>
            <h1>测试文章标题</h1>
            <div class="article-content">
                <p>这是测试内容</p>
                <p>更多内容...</p>
            </div>
            <div class="breadcrumb">
                <a href="#">首页</a>
                <a href="#">API文档</a>
                <a href="#">kintone REST API</a>
            </div>
            <time datetime="2024-01-01">2024年1月1日</time>
        </body>
    </html>
    """


class TestKintoneScraper:
    """测试KintoneScraper类"""
    
    def test_init(self, scraper):
        """测试初始化"""
        assert scraper.base_url == "https://cybozudev.kf5.com/hc/"
        assert scraper.output_dir == Path("test_output")
        assert len(scraper.visited_urls) == 0
    
    @patch('requests.Session.get')
    def test_get_page_content(self, mock_get, scraper, mock_html):
        """测试获取页面内容"""
        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_html
        mock_response.encoding = 'utf-8'
        mock_get.return_value = mock_response
        
        # 测试获取内容
        soup = scraper._get_page_content("http://example.com")
        
        assert soup is not None
        assert soup.title.string == "测试页面"
        assert "http://example.com" in scraper.visited_urls
    
    @patch('requests.Session.get')
    def test_extract_article_content(self, mock_get, scraper, mock_html):
        """测试提取文章内容"""
        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_html
        mock_response.encoding = 'utf-8'
        mock_get.return_value = mock_response
        
        # 创建测试section
        section = Section(
            url="http://example.com/section",
            title="测试Section",
            category_path="API文档/kintone REST API"
        )
        
        # 测试提取文章
        article = scraper._extract_article_content("http://example.com/article", section)
        
        assert article is not None
        assert article.title == "测试文章标题"
        assert "这是测试内容" in article.content
        assert article.category == "kintone REST API"
        assert article.last_updated == "2024-01-01"
    
    def test_organize_by_categories(self, scraper):
        """测试按分类组织"""
        # 创建sections，手动设置article_count
        section1 = Section(
            url="http://example.com/section1",
            title="REST API基础",
            category_path="API文档/kintone REST API"
        )
        section1.article_count = 5
        
        section2 = Section(
            url="http://example.com/section2", 
            title="JavaScript API基础",
            category_path="API文档/kintone JavaScript API"
        )
        section2.article_count = 3
        
        section3 = Section(
            url="http://example.com/section3",
            title="插件开发入门",
            category_path="插件/插件开发"
        )
        section3.article_count = 4
        
        sections = [section1, section2, section3]
        
        categories = scraper._organize_by_categories(sections)
        
        assert len(categories) == 2  # API文档 和 插件
        
        api_category = next(cat for cat in categories if cat.name == "API文档")
        assert api_category.total_articles == 8  # 5 + 3
        assert len(api_category.sections) == 2
        
        plugin_category = next(cat for cat in categories if cat.name == "插件")
        assert plugin_category.total_articles == 4
        assert len(plugin_category.sections) == 1


class TestModels:
    """测试数据模型"""
    
    def test_article_model(self):
        """测试Article模型"""
        article = Article(
            url="http://example.com",
            title="测试文章",
            content="这是测试内容" * 100  # 长内容
        )
        
        assert article.content_length == len("这是测试内容" * 100)
        assert article.scraped_at is not None
        
        # 测试转换为字典
        data = article.to_dict()
        assert data['title'] == "测试文章"
        assert data['content_length'] == article.content_length
        
        # 测试从字典创建
        new_article = Article.from_dict(data)
        assert new_article.title == article.title
        assert new_article.content == article.content
    
    def test_section_model(self):
        """测试Section模型"""
        section = Section(
            url="http://example.com/section",
            title="测试Section",
            articles=["http://example.com/article1", "http://example.com/article2"]
        )
        
        assert section.article_count == 2
        
        # 测试转换
        data = section.to_dict()
        assert len(data['articles']) == 2
        
        new_section = Section.from_dict(data)
        assert new_section.title == section.title
        assert len(new_section.articles) == 2


@pytest.mark.integration
class TestIntegration:
    """集成测试"""
    
    @patch('requests.Session.get')
    def test_scrape_single_section(self, mock_get, scraper):
        """测试抓取单个section"""
        # 模拟section页面
        section_html = """
        <html>
            <body>
                <h1>kintone REST API</h1>
                <a href="/hc/kb/article/123">文章1</a>
                <a href="/hc/kb/article/456">文章2</a>
            </body>
        </html>
        """
        
        # 模拟文章页面
        article_html = """
        <html>
            <body>
                <h1>API基础</h1>
                <div class="article-content">API使用说明</div>
            </body>
        </html>
        """
        
        def mock_response(url):
            response = Mock()
            response.status_code = 200
            response.encoding = 'utf-8'
            
            if 'section' in url:
                response.text = section_html
            else:
                response.text = article_html
                
            return response
        
        mock_get.side_effect = lambda url, **kwargs: mock_response(url)
        
        # 测试提取section信息
        section = scraper._extract_section_info("http://example.com/section")
        
        assert section is not None
        assert section.title == "kintone REST API"
        assert section.article_count == 2
        
        # 测试提取文章
        article = scraper._extract_article_content(section.articles[0], section)
        assert article is not None
        assert article.title == "API基础"
