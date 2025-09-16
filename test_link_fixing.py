#!/usr/bin/env python3
"""测试改进后的链接处理逻辑"""

from src.kintone_scraper.config import get_article_file_path, calculate_relative_path

def test_path_generation():
    """测试文件路径生成功能"""
    print("=== 测试文件路径生成 ===")

    # 测试用例
    test_cases = [
        ("1427187", "新手教程/kintone自定义技巧", "使用TypeScript开发kintone自定义"),
        ("1007997", "插件/插件范例", "甘特图插件"),
        ("1465343", "新手教程/kintone自定义技巧", "向JavaScript自定义中级开发者的目标前进（5）〜TypeScript导入篇〜"),
    ]

    for article_id, category, title in test_cases:
        path = get_article_file_path(article_id, category, title)
        print(f"文章ID: {article_id}")
        print(f"分类: {category}")
        print(f"标题: {title}")
        print(f"生成路径: {path}")
        print("-" * 50)

def test_relative_path_calculation():
    """测试相对路径计算功能"""
    print("\n=== 测试相对路径计算 ===")

    # 测试用例
    test_cases = [
        ("新手教程_kintone自定义技巧/1427187_使用TypeScript开发kintone自定义.html",
         "新手教程_kintone自定义技巧/1465343_向JavaScript自定义中级开发者的目标前进（5）〜TypeScript导入篇〜.html"),
        ("插件_插件范例/1007997_甘特图插件.html",
         "新手教程_kintone自定义技巧/1427187_使用TypeScript开发kintone自定义.html"),
        ("其他/unknown.html",
         "插件_插件范例/1007997_甘特图插件.html"),
    ]

    for from_path, to_path in test_cases:
        relative_path = calculate_relative_path(from_path, to_path)
        print(f"从: {from_path}")
        print(f"到: {to_path}")
        print(f"相对路径: {relative_path}")
        print("-" * 50)

if __name__ == "__main__":
    test_path_generation()
    test_relative_path_calculation()






