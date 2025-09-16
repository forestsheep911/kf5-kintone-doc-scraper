"""pytest配置文件"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from kintone_scraper.models import Article, Section, Category
from tests.fixtures.sample_data import (
    create_sample_article, create_sample_section, create_sample_category,
    SAMPLE_HTML_WITH_IMAGES, SAMPLE_HTML_NO_IMAGES, MOCK_RESPONSES
)


@pytest.fixture
def temp_dir():
    """临时目录fixture"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_article():
    """示例文章fixture"""
    return create_sample_article()


@pytest.fixture
def sample_section():
    """示例章节fixture"""
    return create_sample_section()


@pytest.fixture
def sample_category():
    """示例分类fixture"""
    return create_sample_category()


@pytest.fixture
def mock_requests_get():
    """模拟requests.get的fixture"""
    def _mock_get(url, **kwargs):
        response = Mock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.headers = {'content-type': 'text/html; charset=utf-8'}
        
        # 根据URL返回不同的内容
        if 'section' in url:
            response.text = MOCK_RESPONSES['section_page']
        elif 'article' in url:
            response.text = MOCK_RESPONSES['article_page']
        else:
            response.text = MOCK_RESPONSES['main_page']
        
        return response
    
    return _mock_get


@pytest.fixture
def mock_image_response():
    """模拟图片响应的fixture"""
    def _mock_image_response(url, **kwargs):
        response = Mock()
        response.status_code = 200
        response.headers = {'content-type': 'image/jpeg'}
        response.iter_content.return_value = [b'fake_image_data_chunk_1', b'fake_image_data_chunk_2']
        return response
    
    return _mock_image_response


# pytest标记定义
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "manual: marks tests as manual tests"
    )


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    for item in items:
        # 自动添加标记
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "manual" in str(item.fspath):
            item.add_marker(pytest.mark.manual)
        
        # 为集成测试添加slow标记
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.slow)

