"""测试工具函数"""

import pytest
from pathlib import Path
import tempfile
import json

from kintone_scraper.utils import (
    save_json, load_json, save_markdown, sanitize_filename,
    format_file_size, format_duration, validate_url, chunk_list,
    progress_bar, estimate_time_remaining, ProgressTracker
)


class TestFileOperations:
    """测试文件操作函数"""
    
    def test_save_and_load_json(self):
        """测试JSON保存和加载"""
        test_data = {
            'title': '测试数据',
            'items': [1, 2, 3],
            'nested': {'key': 'value'}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.json"
            
            # 保存JSON
            save_json(test_data, file_path)
            assert file_path.exists()
            
            # 加载JSON
            loaded_data = load_json(file_path)
            assert loaded_data == test_data
    
    def test_load_nonexistent_json(self):
        """测试加载不存在的JSON文件"""
        nonexistent_path = Path("nonexistent.json")
        result = load_json(nonexistent_path)
        assert result is None
    
    def test_save_markdown(self):
        """测试Markdown保存"""
        title = "测试文章"
        content = "这是测试内容\n\n包含多行文本"
        metadata = {
            "分类": "API文档",
            "更新时间": "2024-01-01"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.md"
            
            save_markdown(title, content, metadata, file_path)
            assert file_path.exists()
            
            # 验证内容
            with open(file_path, 'r', encoding='utf-8') as f:
                saved_content = f.read()
            
            assert title in saved_content
            assert content in saved_content
            assert "分类" in saved_content
            assert "API文档" in saved_content


class TestStringUtils:
    """测试字符串处理函数"""
    
    def test_sanitize_filename(self):
        """测试文件名清理"""
        # 测试特殊字符替换
        assert sanitize_filename("文件/名称") == "文件_名称"
        assert sanitize_filename("test:file") == "test：file"
        assert sanitize_filename("file*name") == "file＊name"
        
        # 测试长度限制
        long_name = "a" * 150
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50
        assert result.endswith("...")
    
    def test_format_file_size(self):
        """测试文件大小格式化"""
        assert format_file_size(0) == "0B"
        assert format_file_size(1024) == "1.0KB"
        assert format_file_size(1024 * 1024) == "1.0MB"
        assert format_file_size(1024 * 1024 * 1024) == "1.0GB"
    
    def test_format_duration(self):
        """测试时间格式化"""
        assert format_duration(30) == "30.0秒"
        assert format_duration(90) == "1.5分钟"
        assert format_duration(3660) == "1.0小时"
    
    def test_validate_url(self):
        """测试URL验证"""
        assert validate_url("https://example.com") == True
        assert validate_url("http://test.org/path") == True
        assert validate_url("ftp://files.com") == True
        
        assert validate_url("not-a-url") == False
        assert validate_url("") == False
        assert validate_url("://missing-scheme") == False


class TestListUtils:
    """测试列表处理函数"""
    
    def test_chunk_list(self):
        """测试列表分块"""
        test_list = list(range(10))
        
        chunks = chunk_list(test_list, 3)
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[1] == [3, 4, 5]
        assert chunks[2] == [6, 7, 8]
        assert chunks[3] == [9]
    
    def test_chunk_empty_list(self):
        """测试空列表分块"""
        chunks = chunk_list([], 3)
        assert chunks == []
    
    def test_chunk_single_item(self):
        """测试单项列表分块"""
        chunks = chunk_list([1], 3)
        assert chunks == [[1]]


class TestProgressUtils:
    """测试进度相关函数"""
    
    def test_progress_bar(self):
        """测试进度条生成"""
        # 测试正常进度
        bar = progress_bar(50, 100, width=20)
        assert "[" in bar and "]" in bar
        assert "50%" in bar
        assert "(50/100)" in bar
        
        # 测试完成状态
        bar = progress_bar(100, 100, width=20)
        assert "100%" in bar
        
        # 测试零总数
        bar = progress_bar(0, 0, width=20)
        assert "100%" in bar
    
    def test_estimate_time_remaining(self):
        """测试剩余时间估算"""
        import time
        
        start_time = time.time() - 10  # 10秒前开始
        remaining = estimate_time_remaining(start_time, 50, 100)
        
        # 应该返回格式化的时间字符串
        assert isinstance(remaining, str)
        assert remaining != "未知"
    
    def test_progress_tracker(self):
        """测试进度跟踪器"""
        tracker = ProgressTracker(10, "测试进度")
        
        assert tracker.total == 10
        assert tracker.current == 0
        assert tracker.description == "测试进度"
        
        # 测试更新
        tracker.update(5)
        assert tracker.current == 5
        
        # 测试完成
        tracker.finish()
        assert tracker.current == tracker.total

