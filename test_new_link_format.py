#!/usr/bin/env python3
"""测试新的文章ID引用链接格式"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from kintone_scraper.image_downloader import ImageDownloader
from kintone_scraper.config import get_safe_filename

def test_new_link_format():
    """测试新的链接格式生成"""
    print("=== 测试新的文章ID引用链接格式 ===")
    
    # 创建ImageDownloader实例
    from pathlib import Path
    downloader = ImageDownloader("https://cybozudev.kf5.com", Path("test_output"))
    
    # 测试HTML内容，包含内部文章链接
    test_html = '''
    <div>
        <p>请参考<a href="https://cybozudev.kf5.com/hc/kb/article/1000539/">kintone 插件JavaScript API</a>文档。</p>
        <p>另外，请查看<a href="https://cybozudev.kf5.com/hc/kb/article/1314443/">kintone插件开发入门【Part3】</a>。</p>
        <p>这是一个<a href="https://cybozudev.kf5.com/hc/kb/article/1314677/#section1">当前文章的锚点链接</a>。</p>
        <p>外部链接：<a href="https://google.com">Google</a></p>
    </div>
    '''
    
    # 处理HTML
    processed_html, _ = downloader.process_html_images(
        test_html,
        article_title="kintone插件开发入门【Part2： 信息的隐藏方法篇】",
        article_url="https://cybozudev.kf5.com/hc/kb/article/1314677/",
        article_category="插件/插件开发",
        current_section_category="插件/插件开发"
    )
    
    print("处理后的HTML:")
    print(processed_html)
    print("\n" + "="*50)
    
    # 检查是否包含预期的格式
    if 'data-article-id="1000539"' in processed_html:
        print("✅ 文章链接1000539转换成功")
    else:
        print("❌ 文章链接1000539转换失败")
        
    if 'data-article-id="1314443"' in processed_html:
        print("✅ 文章链接1314443转换成功")
    else:
        print("❌ 文章链接1314443转换失败")
        
    if 'class="article-link"' in processed_html:
        print("✅ article-link class添加成功")
    else:
        print("❌ article-link class添加失败")
        
    if 'href="#"' in processed_html:
        print("✅ 空href设置成功")
    else:
        print("❌ 空href设置失败")

if __name__ == "__main__":
    test_new_link_format()
