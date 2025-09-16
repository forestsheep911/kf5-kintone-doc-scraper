#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试改进后的抓取器 - 只提取<article>标签内容
"""

import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kintone_scraper.scraper import KintoneScraper
from kintone_scraper.models import Section

def test_improved_article_extraction():
    """测试改进后的文章提取功能"""
    print("🧪 测试改进后的文章提取功能")
    print("="*50)
    
    # 创建抓取器实例
    scraper = KintoneScraper(output_dir=Path("test_output"))
    
    # 测试几篇文章
    test_articles = [
        {
            'url': 'https://cybozudev.kf5.com/hc/kb/article/200733/',
            'expected_title': 'kintone REST API共通规格'
        },
        {
            'url': 'https://cybozudev.kf5.com/hc/kb/article/201594/',
            'expected_title': '获取记录（GET）'
        }
    ]
    
    # 创建一个测试用的section
    test_section = Section(
        url="https://cybozudev.kf5.com/hc/kb/section/106250/",
        title="kintone REST API",
        category_path="API文档/kintone REST API"
    )
    
    for i, test_case in enumerate(test_articles, 1):
        print(f"\n[{i}/{len(test_articles)}] 测试文章: {test_case['url']}")
        
        # 提取文章内容
        article = scraper._extract_article_content(test_case['url'], test_section)
        
        if article:
            print(f"  ✅ 提取成功")
            print(f"  📄 标题: {article.title}")
            print(f"  📊 内容长度: {article.content_length} 字符")
            print(f"  📂 分类: {article.category}")
            print(f"  🔗 Section: {article.section_title}")
            print(f"  📅 更新时间: {article.last_updated}")
            print(f"  📝 内容预览: {article.content[:100]}...")
            
            # 验证标题是否正确提取
            if test_case['expected_title'].lower() in article.title.lower():
                print(f"  ✅ 标题提取正确")
            else:
                print(f"  ⚠️ 标题可能不完整: 期望包含 '{test_case['expected_title']}'")
        else:
            print(f"  ❌ 提取失败")
    
    # 测试完成，不返回值

def test_section_extraction():
    """测试section信息提取"""
    print(f"\n{'='*50}")
    print("🧪 测试Section信息提取")
    print("="*50)
    
    scraper = KintoneScraper(output_dir=Path("test_output"))
    
    # 测试一个section页面
    section_url = "https://cybozudev.kf5.com/hc/kb/section/106250/"
    print(f"测试Section: {section_url}")
    
    section = scraper._extract_section_info(section_url)
    
    if section:
        print(f"  ✅ Section提取成功")
        print(f"  📄 标题: {section.title}")
        print(f"  📊 文章数量: {section.article_count}")
        print(f"  📂 分类路径: {section.category_path}")
        print(f"  📝 描述: {section.description}")
        print(f"  🔗 前5个文章:")
        
        for i, article_url in enumerate(section.articles[:5], 1):
            print(f"    {i}. {article_url}")
    else:
        print(f"  ❌ Section提取失败")

if __name__ == "__main__":
    print("🚀 测试改进后的kintone抓取器")
    print("="*60)
    
    try:
        # 测试文章提取
        test_improved_article_extraction()
        
        # 测试section提取
        test_section_extraction()
        
        print(f"\n{'='*60}")
        print("🎉 所有测试完成！")
        print("💡 抓取器已优化为只提取<article>标签内容")
        print("💡 这样可以避免抓取导航、侧边栏等无关内容")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
