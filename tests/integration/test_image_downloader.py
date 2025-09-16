"""测试图片下载器集成功能"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from kintone_scraper.image_downloader import ImageDownloader, HTMLGenerator


class TestImageDownloader:
    """测试图片下载器"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def downloader(self, temp_dir):
        """图片下载器fixture"""
        return ImageDownloader(
            base_url="https://cybozudev.kf5.com/hc/",
            output_dir=temp_dir
        )
    
    def test_init(self, downloader, temp_dir):
        """测试初始化"""
        assert downloader.base_url == "https://cybozudev.kf5.com/hc/"
        assert downloader.output_dir == temp_dir
        assert (temp_dir / "images").exists()
        assert len(downloader.downloaded_images) == 0
    
    def test_get_image_extension(self, downloader):
        """测试获取图片扩展名"""
        # 从URL获取
        assert downloader._get_image_extension("https://example.com/image.jpg") == ".jpg"
        assert downloader._get_image_extension("https://example.com/image.PNG") == ".png"
        
        # 从Content-Type获取
        assert downloader._get_image_extension("https://example.com/image", "image/jpeg") == ".jpg"
        assert downloader._get_image_extension("https://example.com/image", "image/png") == ".png"
        
        # 默认扩展名
        assert downloader._get_image_extension("https://example.com/unknown") == ".jpg"
    
    def test_generate_filename(self, downloader):
        """测试生成文件名"""
        filename1 = downloader._generate_filename("https://example.com/image1.jpg")
        filename2 = downloader._generate_filename("https://example.com/image2.jpg")
        
        # 不同URL应该生成不同文件名
        assert filename1 != filename2
        
        # 相同URL应该生成相同文件名
        filename3 = downloader._generate_filename("https://example.com/image1.jpg")
        assert filename1 == filename3
        
        # 文件名应该有正确的扩展名
        assert filename1.endswith(".jpg")
    
    def test_is_valid_image_url(self, downloader):
        """测试URL有效性检查"""
        # 有效URL
        assert downloader._is_valid_image_url("https://example.com/image.jpg") == True
        assert downloader._is_valid_image_url("http://test.com/pic.png") == True
        
        # 无效URL
        assert downloader._is_valid_image_url("") == False
        assert downloader._is_valid_image_url("not-a-url") == False
        assert downloader._is_valid_image_url("://missing-scheme") == False
    
    @patch('requests.Session.get')
    def test_download_image_success(self, mock_get, downloader):
        """测试成功下载图片"""
        # 模拟成功响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.iter_content.return_value = [b'fake_image_data']
        mock_get.return_value = mock_response
        
        filename = downloader.download_image("https://example.com/test.jpg")
        
        assert filename is not None
        assert filename.endswith(".jpg")
        assert filename in downloader.downloaded_images.values()
        
        # 检查文件是否真的被创建
        image_path = downloader.images_dir / filename
        assert image_path.exists()
    
    @patch('requests.Session.get')
    def test_download_image_failure(self, mock_get, downloader):
        """测试下载图片失败"""
        # 模拟失败响应
        mock_get.side_effect = Exception("Network error")
        
        filename = downloader.download_image("https://example.com/test.jpg")
        
        assert filename is None
        assert "https://example.com/test.jpg" in downloader.failed_downloads
    
    def test_process_html_images(self, downloader):
        """测试处理HTML中的图片"""
        html_content = '''
        <div>
            <p>Some text</p>
            <img src="https://example.com/image1.jpg" alt="Image 1">
            <p>More text</p>
            <img src="/relative/image2.png" alt="Image 2">
        </div>
        '''
        
        with patch.object(downloader, 'download_image') as mock_download:
            mock_download.side_effect = ["image1.jpg", "image2.png"]
            
            updated_html, downloaded_files = downloader.process_html_images(
                html_content, "测试文章"
            )
            
            # 检查图片链接是否被替换
            assert "../images/image1.jpg" in updated_html
            assert "../images/image2.png" in updated_html
            
            # 检查下载的文件列表
            assert downloaded_files == ["image1.jpg", "image2.png"]
            
            # 检查下载函数被调用
            assert mock_download.call_count == 2
    
    def test_get_download_stats(self, downloader):
        """测试获取下载统计"""
        # 初始状态
        stats = downloader.get_download_stats()
        assert stats['downloaded'] == 0
        assert stats['failed'] == 0
        assert stats['total_attempted'] == 0
        
        # 添加一些数据
        downloader.downloaded_images['url1'] = 'file1.jpg'
        downloader.downloaded_images['url2'] = 'file2.jpg'
        downloader.failed_downloads.add('url3')
        
        stats = downloader.get_download_stats()
        assert stats['downloaded'] == 2
        assert stats['failed'] == 1
        assert stats['total_attempted'] == 3


class TestHTMLGenerator:
    """测试HTML生成器"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def generator(self, temp_dir):
        """HTML生成器fixture"""
        return HTMLGenerator(temp_dir)
    
    def test_init(self, generator, temp_dir):
        """测试初始化"""
        assert generator.output_dir == temp_dir
        assert (temp_dir / "html").exists()
    
    def test_get_html_template(self, generator):
        """测试HTML模板"""
        template = generator._get_html_template()
        
        assert isinstance(template, str)
        assert len(template) > 0
        assert "<!DOCTYPE html>" in template
        assert "{title}" in template
        assert "{content}" in template
    
    def test_generate_article_html(self, generator):
        """测试生成文章HTML"""
        # 创建模拟文章对象
        article = Mock()
        article.title = "测试文章"
        article.category = "API文档"
        article.section_title = "REST API"
        article.last_updated = "2024-01-01"
        article.url = "https://example.com/article/123"
        article.scraped_at = "2024-01-01T00:00:00"
        article.content_length = 1000
        
        html_content = "<p>这是文章内容</p>"
        images = ["image1.jpg", "image2.png"]
        
        html_file = generator.generate_article_html(article, html_content, images)
        
        assert html_file is not None
        assert html_file.exists()
        assert html_file.suffix == ".html"
        
        # 检查生成的HTML内容
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "测试文章" in content
        assert "API文档" in content
        assert "这是文章内容" in content
        assert "2 张" in content  # 图片数量
    
    def test_generate_index_html(self, generator):
        """测试生成索引页面"""
        # 创建模拟数据
        categories = []
        articles = [
            Mock(title="文章1", category="API文档", content_length=1000, last_updated="2024-01-01"),
            Mock(title="文章2", category="插件", content_length=2000, last_updated="2024-01-02"),
        ]
        
        index_file = generator.generate_index_html(categories, articles)
        
        assert index_file is not None
        assert index_file.exists()
        assert index_file.name == "index.html"
        
        # 检查内容
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "kintone开发者文档" in content
        assert "2" in content  # 文章数量
        assert "文章1" in content
        assert "文章2" in content

