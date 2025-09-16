#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kintone抓取器运行脚本
支持不同的运行模式：测试、小批量、全量
"""

import sys
import argparse
import subprocess
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kintone_scraper.scraper import KintoneScraper


def _inject_copy_buttons(base_output: Path) -> None:
    """在生成输出后，为该输出目录的 HTML 注入复制按钮。"""
    html_dir = base_output / "html"
    if not html_dir.exists():
        print(f"⚠ 未找到 HTML 目录，跳过注入: {html_dir}")
        return
    script = Path(__file__).parent / "inject_copy_buttons.py"
    if not script.exists():
        print(f"⚠ 未找到注入脚本，跳过: {script}")
        return
    try:
        print(f"🔧 正在为 {html_dir} 注入复制按钮...")
        proc = subprocess.run([sys.executable, str(script), str(html_dir)], capture_output=True, text=True)
        out = (proc.stdout or '').strip()
        err = (proc.stderr or '').strip()
        if out:
            print(out)
        if err:
            print(f"注入提示: {err}")
    except Exception as e:
        print(f"⚠ 注入过程出错: {e}")

def run_test_mode(output_dir: Path, try_external_images: bool = True):
    """测试模式：只抓取1个section的前3篇文章"""
    print("🧪 测试模式：抓取少量文章验证功能")
    print("="*60)
    
    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images
    )
    
    # 测试两个section：一个普通的API文档，一个包含大量图片的插件文档
    test_sections = [
        "https://cybozudev.kf5.com/hc/kb/section/106250/",  # kintone REST API (普通文档)
        "https://cybozudev.kf5.com/hc/kb/section/1180832/"   # 插件开发 (包含101张图片的文章)
    ]

    total_success = 0
    total_articles = 0

    for section_idx, section_url in enumerate(test_sections, 1):
        print(f"\n🎯 Section {section_idx}/2: {section_url}")

        section = scraper._extract_section_info(section_url)
        if not section:
            print("❌ Section提取失败")
            continue

        print(f"✅ Section: {section.title} ({section.article_count}篇文章)")
        print(f"📂 分类: {section.category_path}")

        # 根据section类型决定抓取数量
        if "插件开发" in section.title:
            # 插件开发section，优先抓取包含图片的文章
            max_articles = min(5, len(section.articles))  # 多抓几篇找到图片文章
            print(f"🔄 抓取前{max_articles}篇文章（查找图片文章）...")
        else:
            # 普通section，只抓取前2篇
            max_articles = min(2, len(section.articles))
            print(f"🔄 抓取前{max_articles}篇文章...")

        success_count = 0
        for i, article_url in enumerate(section.articles[:max_articles], 1):
            print(f"  [{i}/{max_articles}] {article_url}")

            article = scraper._extract_article_content(article_url, section)
            if article:
                print(f"    ✅ {article.title}")
                print(f"    📊 {article.content_length}字符")

                scraper._save_article_files(article, section)
                scraper.result.add_article(article, success=True)
                success_count += 1
                total_success += 1
            else:
                print(f"    ❌ 抓取失败")
                scraper.result.failed_articles += 1

        total_articles += max_articles
        print(f"  📊 Section结果: {success_count}/{max_articles} 成功")

    # 保存结果
    scraper._save_results()

    print(f"\n📊 测试结果:")
    print(f"  成功: {total_success}/{total_articles}")
    print(f"  输出目录: {output_dir.absolute()}")

    # 获取图片下载统计
    if scraper.image_downloader:
        stats = scraper.image_downloader.get_download_stats()
        print(f"  图片下载: 成功{stats['images_downloaded']}, 失败{stats['failed']}")
        if stats.get('attachments_downloaded', 0) > 0:
            print(f"  附件下载: 成功{stats['attachments_downloaded']}")

    return total_success == total_articles

def run_small_batch(output_dir: Path, try_external_images: bool = True):
    """小批量模式：抓取所有section，每个最多2篇文章"""
    print("📦 小批量模式：抓取所有section的部分文章")
    print("="*60)
    
    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images
    )
    
    # 获取所有sections
    print("🔍 正在获取所有section链接...")
    test_sections = scraper._extract_section_links()
    
    if not test_sections:
        print("❌ 未找到任何section")
        return False
    
    print(f"📋 发现 {len(test_sections)} 个section")
    
    total_articles = 0
    max_per_section = 2
    
    for i, section_url in enumerate(test_sections, 1):
        print(f"\n🎯 Section {i}/{len(test_sections)}: {section_url}")
        
        section = scraper._extract_section_info(section_url)
        if not section:
            print("❌ Section提取失败")
            continue
        
        print(f"✅ Section: {section.title} ({section.article_count}篇文章)")
        print(f"📂 分类: {section.category_path}")
        
        # 抓取指定数量的文章
        max_articles = min(max_per_section, len(section.articles))
        print(f"🔄 抓取前{max_articles}篇文章...")
        
        for j, article_url in enumerate(section.articles[:max_articles], 1):
            print(f"  [{j}/{max_articles}] {article_url}")
            
            article = scraper._extract_article_content(article_url, section)
            if article:
                print(f"    ✅ {article.title} ({article.content_length}字符)")
                scraper._save_article_files(article, section)
                scraper.result.add_article(article, success=True)
                total_articles += 1
            else:
                print(f"    ❌ 提取失败")
                scraper.result.failed_articles += 1
    
    # 保存结果
    scraper._save_results()
    
    print(f"\n📊 小批量结果:")
    print(f"  成功文章: {scraper.result.successful_articles}")
    print(f"  失败文章: {scraper.result.failed_articles}")
    print(f"  输出目录: {output_dir.absolute()}")
    
    if scraper.image_downloader:
        stats = scraper.image_downloader.get_download_stats()
        print(f"  图片下载: 成功{stats['images_downloaded']}, 失败{stats['failed']}")
        if stats.get('attachments_downloaded', 0) > 0:
            print(f"  附件下载: 成功{stats['attachments_downloaded']}")

def run_tiny_batch(output_dir: Path, try_external_images: bool = True, use_api: bool = False):
    """微型模式：抓取所有section，每个最多1篇文章，支持API和网页两种抓取方式"""
    if use_api:
        print("🔬 微型模式（API）：通过 API 列表驱动抓取少量文章")
    else:
        print("🔬 微型模式（网页）：抓取所有section的单篇文章")
    print("="*60)
    
    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images
    )
    
    if use_api:
        # API模式：使用修复后的API抓取逻辑，但限制数量
        if not scraper.kf5:
            print("❌ KF5 API 未配置，无法使用API模式")
            return False
        
        print("🗂️  构建分类映射...")
        forum_mapping = scraper.kf5.build_category_mapping()
        print(f"📋 获取到 {len(forum_mapping)} 个分类映射")
        
        # 改进的API模式：从更多文章中按分类去重，确保每个分类都有代表
        from kintone_scraper.models import Section
        from kintone_scraper.utils import make_progress, rate_limit
        from kintone_scraper.config import REQUEST_DELAY
        from urllib.parse import urljoin
        
        # 按分类收集文章，每个分类最多1篇
        category_articles = {}
        seen_categories = set()
        
        # 获取更多页面的文章来确保覆盖所有分类
        all_posts = []
        for page in range(1, 6):  # 获取前5页文章，每页100篇，总共500篇
            try:
                data = scraper.kf5.list_all_posts(page=page, per_page=100)
                posts = data.get('posts') or data.get('data') or data.get('items') or []
                if not posts:
                    break  # 没有更多文章了
                all_posts.extend(posts)
                print(f"📄 第{page}页: 获取 {len(posts)} 篇文章")
            except Exception as e:
                print(f"⚠️  获取第{page}页文章失败: {e}")
                break
        
        print(f"API 返回原始文章: {len(all_posts)} 篇")
        
        # 按分类去重，每个分类只保留第一篇文章
        for post in all_posts:
            forum_id = post.get('forum_id')
            forum_name = post.get('forum_name', '')
            
            # 构建分类标识
            if forum_id and forum_id in forum_mapping:
                category_key = forum_mapping[forum_id]['full_path']
                post['forum_name'] = forum_mapping[forum_id]['forum_name']  # 使用映射中的名称
            elif forum_name:
                category_key = f"其他/{forum_name}"
            else:
                category_key = "其他/未知"
            
            # 每个分类只保留第一篇文章
            if category_key not in seen_categories:
                seen_categories.add(category_key)
                category_articles[category_key] = post
                print(f"📂 {category_key}: 选择文章 {post.get('id')} - {post.get('title', '')[:50]}...")
        
        filtered_items = list(category_articles.values())
        total_articles = len(filtered_items)
        scraper.result.total_articles = total_articles
        print(f"最终收集文章: {total_articles} 篇（覆盖 {len(seen_categories)} 个分类）")

        article_progress = make_progress(total_articles, "抓取文章:")
        for i, it in enumerate(filtered_items, 1):
            aid = str(it.get('id') or '').strip()
            url = (it.get('url') or '').strip()
            title = (it.get('title') or '').strip()
            forum_id = it.get('forum_id')
            forum_name = it.get('forum_name', '')
            
            if not url and aid:
                url = f"/hc/kb/article/{aid}/"
            elif url and '/hc/kb/article/' not in url and aid:
                url = f"/hc/kb/article/{aid}/"
                
            if not (aid or url):
                continue
                
            article_url = urljoin(scraper.base_url, url)
            
            # 构建正确的分类信息
            category_path = "其他/未知"
            if forum_id and forum_id in forum_mapping:
                category_path = forum_mapping[forum_id]['full_path']
            elif forum_name:
                category_path = f"其他/{forum_name}"
            
            article_section = Section(
                url="", 
                title=forum_name or '未知分类', 
                description="", 
                articles=[], 
                category_path=category_path
            )
            
            print(f"  [{i}/{total_articles}] {article_url}")
            print(f"    📂 分类: {category_path}")
            
            article = scraper._extract_article_content(article_url, article_section)
            if article:
                print(f"    ✅ {article.title} ({article.content_length}字符)")
                scraper._save_article_files(article, article_section)
                scraper.result.add_article(article, success=True)
            else:
                print(f"    ❌ 提取失败")
                scraper.result.failed_articles += 1
                
            article_progress.update()
            rate_limit(REQUEST_DELAY)
            
        article_progress.finish()
        
    else:
        # 网页模式：类似small模式但每个section只抓1篇
        print("🔍 正在获取所有section链接...")
        test_sections = scraper._extract_section_links()
        
        if not test_sections:
            print("❌ 未找到任何section")
            return False
        
        print(f"📋 发现 {len(test_sections)} 个section")
        
        total_articles = 0
        max_per_section = 1  # tiny模式每个section只抓1篇
        
        for i, section_url in enumerate(test_sections, 1):
            print(f"\n🎯 Section {i}/{len(test_sections)}: {section_url}")
            
            section = scraper._extract_section_info(section_url)
            if not section:
                print("❌ Section提取失败")
                continue
            
            print(f"✅ Section: {section.title} ({section.article_count}篇文章)")
            print(f"📂 分类: {section.category_path}")
            
            # 抓取指定数量的文章
            max_articles = min(max_per_section, len(section.articles))
            print(f"🔄 抓取前{max_articles}篇文章...")
            
            for j, article_url in enumerate(section.articles[:max_articles], 1):
                print(f"  [{j}/{max_articles}] {article_url}")
                
                article = scraper._extract_article_content(article_url, section)
                if article:
                    print(f"    ✅ {article.title} ({article.content_length}字符)")
                    scraper._save_article_files(article, section)
                    scraper.result.add_article(article, success=True)
                    total_articles += 1
                else:
                    print(f"    ❌ 提取失败")
                    scraper.result.failed_articles += 1
    
    # 保存结果
    scraper._save_results()
    
    print(f"\n📊 微型模式结果:")
    print(f"  成功文章: {scraper.result.successful_articles}")
    print(f"  失败文章: {scraper.result.failed_articles}")
    print(f"  输出目录: {output_dir.absolute()}")
    
    if scraper.image_downloader:
        stats = scraper.image_downloader.get_download_stats()
        print(f"  图片下载: 成功{stats['images_downloaded']}, 失败{stats['failed']}")
        if stats.get('attachments_downloaded', 0) > 0:
            print(f"  附件下载: 成功{stats['attachments_downloaded']}")
    
    return True

def run_full_scrape(output_dir: Path, try_external_images: bool = True):
    """全量模式：抓取所有文档"""
    print("🌍 全量模式：抓取所有kintone文档")
    print("="*60)
    print("⚠️  这将需要较长时间，请确保网络连接稳定")
    
    confirm = input("确认开始全量抓取？(y/N): ")
    if confirm.lower() != 'y':
        print("❌ 用户取消")
        return
    
    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images
    )
    
    # 运行完整抓取
    result = scraper.scrape_all()
    
    print(f"\n📊 全量抓取完成:")
    print(f"  成功文章: {result.successful_articles}")
    print(f"  失败文章: {result.failed_articles}")
    print(f"  成功率: {result.get_success_rate():.1%}")
    print(f"  耗时: {result.duration}")
    
    if scraper.image_downloader:
        stats = scraper.image_downloader.get_download_stats()
        print(f"  图片下载: 成功{stats['images_downloaded']}, 失败{stats['failed']}")
        if stats.get('attachments_downloaded', 0) > 0:
            print(f"  附件下载: 成功{stats['attachments_downloaded']}")

def main():
    parser = argparse.ArgumentParser(description="kintone文档抓取器")
    parser.add_argument(
        "mode",
        choices=["test", "small", "tiny", "full"],
        help="运行模式: test(测试3篇), small(小批量), tiny(每section1篇), full(全量)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output"),
        help="输出目录 (默认: output)"
    )
    parser.add_argument(
        "--skip-external-images",
        action="store_true",
        help="跳过外部图床的图片下载 (默认会尝试下载)"
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="使用 KF5 API 列表驱动抓取（更完整，不易漏文）"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="不跳过已存在的文章（默认会跳过以节省时间）"
    )
    
    args = parser.parse_args()
    
    # 根据模式创建不同的输出目录
    if args.output == Path("output"):  # 使用默认输出目录
        output_dir = Path(f"output_{args.mode}")
    else:  # 用户指定了输出目录
        output_dir = args.output / args.mode
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📂 输出目录: {output_dir.absolute()}")
    print(f"🎯 运行模式: {args.mode}")
    print()
    
    try:
        if args.mode == "test":
            success = run_test_mode(output_dir, not args.skip_external_images)
            if success:
                print(f"\n🎉 测试成功！结果保存在: {output_dir}")
                print("可以尝试 small 模式")
            else:
                print("\n❌ 测试失败，请检查问题")
        
        elif args.mode == "small":
            run_small_batch(output_dir, not args.skip_external_images)
            print(f"\n🎉 小批量完成！结果保存在: {output_dir}")
            print("如果效果满意，可以运行 full 模式")

        elif args.mode == "tiny":
            success = run_tiny_batch(
                output_dir, 
                not args.skip_external_images, 
                use_api=args.use_api
            )
            if success:
                print(f"\n🎉 微型模式完成！结果保存在: {output_dir}")
                if args.use_api:
                    print("💡 API模式测试完成，可以验证分类是否正确")
                else:
                    print("💡 网页模式测试完成，可以尝试 --use-api 测试API模式")
            else:
                print("\n❌ 微型模式失败，请检查配置")

        elif args.mode == "full":
            if args.use_api:
                print("🌍 全量模式（API）：通过 API 列表驱动抓取")
                scraper = KintoneScraper(
                    output_dir=output_dir,
                    enable_images=True,
                    try_external_images=not args.skip_external_images,
                    skip_existing=(not args.no_skip_existing)
                )
                res = scraper.scrape_all_via_api()
                print(f"\n📊 全量抓取完成(基于API): 成功{res.successful_articles}/{res.total_articles}")
            else:
                # 非 API 路径下也应用跳过逻辑
                scraper = KintoneScraper(
                    output_dir=output_dir,
                    enable_images=True,
                    try_external_images=not args.skip_external_images,
                    skip_existing=(not args.no_skip_existing)
                )
                # 复用 scrape_all 的实现
                res = scraper.scrape_all()
                print(f"\n📊 全量抓取完成: 成功{res.successful_articles}/{res.total_articles}")
            print(f"\n🎉 全量抓取完成！结果保存在: {output_dir}")
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
    # 统一在结束后注入复制按钮
    _inject_copy_buttons(output_dir)

if __name__ == "__main__":
    main()
