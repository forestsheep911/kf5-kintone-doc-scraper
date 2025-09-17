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
from typing import Optional

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kintone_scraper.scraper import KintoneScraper
from kintone_scraper.models import ScrapingResult


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

def run_test_mode(output_dir: Path, try_external_images: bool = True, article_workers: Optional[int] = None):
    """测试模式：只抓取1个section的前3篇文章"""
    print("🧪 测试模式：抓取少量文章验证功能")
    print("="*60)
    
    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images,
        article_workers=article_workers
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



def run_small_batch(output_dir: Path, try_external_images: bool = True, skip_existing: bool = True, use_api: bool = False, article_workers: Optional[int] = None) -> Optional[ScrapingResult]:
    """小批量模式：抓取所有section，每个最多3篇文章"""
    print("📦 小批量模式：每个分类抓取至多 3 篇文章")
    print("="*60)

    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images,
        skip_existing=skip_existing,
        article_workers=article_workers
    )

    if use_api:
        if not scraper.kf5:
            print("❌ KF5 API 未配置，无法使用API模式")
            return None
        result = scraper.scrape_all_via_api(per_category_limit=3)
    else:
        result = scraper.scrape_all(section_article_limit=3)

    print()
    print("📊 小批量结果:")
    print(f"  计划文章: {result.total_articles}")
    print(f"  成功文章: {result.successful_articles}")
    print(f"  失败文章: {result.failed_articles}")
    print(f"  输出目录: {output_dir.absolute()}")

    if scraper.image_downloader:
        stats = scraper.image_downloader.get_download_stats()
        print(f"  图片下载: 成功{stats['images_downloaded']}, 失败{stats['failed']}")
        if stats.get('attachments_downloaded', 0) > 0:
            print(f"  附件下载: 成功{stats['attachments_downloaded']}")

    if result.failed_details:
        print("  ⚠️ 未抓取的文章:")
        for detail in result.failed_details:
            print(f"    - {detail}")

    return result


def run_tiny_batch(output_dir: Path, try_external_images: bool = True, skip_existing: bool = True, use_api: bool = False, article_workers: Optional[int] = None) -> Optional[ScrapingResult]:
    """微型模式：抓取所有section，每个最多1篇文章，支持API和网页两种抓取方式"""
    if use_api:
        print("🔬 微型模式（API）：通过 API 列表驱动抓取少量文章")
    else:
        print("🔬 微型模式（网页）：抓取所有section的单篇文章")
    print("="*60)

    scraper = KintoneScraper(
        output_dir=output_dir,
        enable_images=True,
        try_external_images=try_external_images,
        skip_existing=skip_existing,
        article_workers=article_workers
    )

    if use_api:
        if not scraper.kf5:
            print("❌ KF5 API 未配置，无法使用API模式")
            return None
        result = scraper.scrape_all_via_api(per_category_limit=1)
    else:
        result = scraper.scrape_all(section_article_limit=1)

    print()
    print("📊 微型模式结果:")
    print(f"  计划文章: {result.total_articles}")
    print(f"  成功文章: {result.successful_articles}")
    print(f"  失败文章: {result.failed_articles}")
    print(f"  输出目录: {output_dir.absolute()}")

    if scraper.image_downloader:
        stats = scraper.image_downloader.get_download_stats()
        print(f"  图片下载: 成功{stats['images_downloaded']}, 失败{stats['failed']}")
        if stats.get('attachments_downloaded', 0) > 0:
            print(f"  附件下载: 成功{stats['attachments_downloaded']}")

    if result.failed_details:
        print("  ⚠️ 未抓取的文章:")
        for detail in result.failed_details:
            print(f"    - {detail}")

    return result


def run_full_scrape(output_dir: Path, try_external_images: bool = True, article_workers: Optional[int] = None):
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
        try_external_images=try_external_images,
        article_workers=article_workers
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
    parser.add_argument(
        "--article-workers",
        type=int,
        help="文章抓取并发线程数（默认4）"
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
            success = run_test_mode(output_dir, not args.skip_external_images, args.article_workers)
            if success:
                print(f"\n🎉 测试成功！结果保存在: {output_dir}")
                print("可以尝试 small 模式")
            else:
                print("\n❌ 测试失败，请检查问题")
        
        elif args.mode == "small":
            result = run_small_batch(
                output_dir,
                not args.skip_external_images,
                skip_existing=(not args.no_skip_existing),
                use_api=args.use_api,
                article_workers=args.article_workers
            )
            if result is None:
                print()
                print("❌ 小批量模式执行失败，请检查日志输出")
            else:
                if result.failed_articles:
                    print()
                    print(f"⚠️ 小批量完成（{result.failed_articles} 篇未抓取），结果保存在: {output_dir}")
                    print("如需补抓，可稍后重试上述文章。")
                else:
                    print()
                    print(f"🎉 小批量完成！结果保存在: {output_dir}")
                    print("如果效果满意，可以运行 full 模式")

        elif args.mode == "tiny":
            result = run_tiny_batch(
                output_dir,
                not args.skip_external_images,
                skip_existing=(not args.no_skip_existing),
                use_api=args.use_api,
                article_workers=args.article_workers
            )
            if result is None:
                print()
                print("❌ 微型模式执行失败，请检查配置")
            else:
                if result.failed_articles:
                    print()
                    print(f"⚠️ 微型模式完成（{result.failed_articles} 篇未抓取），结果保存在: {output_dir}")
                    if args.use_api:
                        print("💡 仍可通过 API 列表或降低并发重试上述文章")
                else:
                    print()
                    print(f"🎉 微型模式完成！结果保存在: {output_dir}")
                    if args.use_api:
                        print("💡 API模式测试完成，可以验证分类是否正确")
                    else:
                        print("💡 网页模式测试完成，可以尝试 --use-api 测试API模式")


        elif args.mode == "full":
            if args.use_api:
                print("🌍 全量模式（API）：通过 API 列表驱动抓取")
                scraper = KintoneScraper(
                    output_dir=output_dir,
                    enable_images=True,
                    try_external_images=not args.skip_external_images,
                    skip_existing=(not args.no_skip_existing),
                    article_workers=args.article_workers
                )
                res = scraper.scrape_all_via_api()
                print(f"\n📊 全量抓取完成(基于API): 成功{res.successful_articles}/{res.total_articles}")
            else:
                # 非 API 路径下也应用跳过逻辑
                scraper = KintoneScraper(
                    output_dir=output_dir,
                    enable_images=True,
                    try_external_images=not args.skip_external_images,
                    skip_existing=(not args.no_skip_existing),
                    article_workers=args.article_workers
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
