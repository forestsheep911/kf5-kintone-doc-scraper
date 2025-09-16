"""命令行接口"""

import logging
from pathlib import Path
from typing import List, Optional

import click

from .config import DEFAULT_OUTPUT_DIR, MAIN_CATEGORIES
from .scraper import KintoneScraper


@click.command()
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help='输出目录路径',
    show_default=True
)
@click.option(
    '--categories', '-c',
    type=str,
    help='指定要抓取的分类，用逗号分隔。例如: "API文档,插件"'
)
@click.option(
    '--base-url',
    type=str,
    default='https://cybozudev.kf5.com/hc/',
    help='基础URL',
    show_default=True
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='显示详细日志'
)
@click.option(
    '--list-categories',
    is_flag=True,
    help='列出所有可用的分类'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='试运行，只显示将要抓取的内容，不实际下载'
)
@click.option(
    '--bilibili-mode',
    type=click.Choice(['link', 'iframe']),
    default='iframe',
    help='B站视频处理模式：iframe=嵌入播放器（推荐），link=生成跳转链接',
    show_default=True
)
def main(
    output: Path,
    categories: Optional[str],
    base_url: str,
    verbose: bool,
    list_categories: bool,
    dry_run: bool,
    bilibili_mode: str
) -> None:
    """
    kintone开发者文档抓取器
    
    自动抓取并整理cybozu开发者网站的所有技术文档，
    按照网站的目录层级进行组织。
    
    示例:
    
        # 抓取所有文档
        kintone-scraper
        
        # 只抓取API文档和插件相关内容
        kintone-scraper -c "API文档,插件"
        
        # 指定输出目录
        kintone-scraper -o ./my_docs
        
        # 显示详细日志
        kintone-scraper -v
    """
    
    # 设置日志级别
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # 列出分类
    if list_categories:
        click.echo("📂 可用的分类:")
        click.echo()
        for main_cat, sub_cats in MAIN_CATEGORIES.items():
            click.echo(f"  📁 {main_cat}")
            for sub_cat in sub_cats:
                click.echo(f"    📄 {sub_cat}")
            click.echo()
        return
    
    # 解析分类参数
    target_categories: Optional[List[str]] = None
    if categories:
        target_categories = [cat.strip() for cat in categories.split(',')]
        
        # 验证分类是否存在
        valid_categories = set(MAIN_CATEGORIES.keys())
        invalid_categories = set(target_categories) - valid_categories
        
        if invalid_categories:
            click.echo(f"❌ 无效的分类: {', '.join(invalid_categories)}", err=True)
            click.echo(f"💡 可用分类: {', '.join(valid_categories)}")
            return
        
        click.echo(f"🎯 将抓取以下分类: {', '.join(target_categories)}")
    
    # 试运行
    if dry_run:
        click.echo("🔍 试运行模式 - 分析网站结构...")
        scraper = KintoneScraper(output_dir=output, base_url=base_url, bilibili_mode=bilibili_mode)
        
        # 获取section信息但不下载内容
        section_links = scraper._extract_section_links()
        click.echo(f"📊 发现 {len(section_links)} 个sections")
        
        total_articles = 0
        for section_url in section_links[:5]:  # 只检查前5个作为示例
            section = scraper._extract_section_info(section_url)
            if section:
                click.echo(f"  📁 {section.title}: {section.article_count} 篇文章")
                total_articles += section.article_count
        
        if len(section_links) > 5:
            click.echo(f"  ... 还有 {len(section_links) - 5} 个sections")
        
        click.echo(f"📈 预估总文章数: {total_articles}+ 篇")
        click.echo("💡 使用 --verbose 查看详细信息")
        return
    
    # 创建抓取器
    scraper = KintoneScraper(output_dir=output, base_url=base_url, bilibili_mode=bilibili_mode)
    
    # 显示开始信息
    click.echo("🚀 kintone开发者文档抓取器")
    click.echo("=" * 50)
    click.echo(f"📂 输出目录: {output.absolute()}")
    click.echo(f"🌐 目标网站: {base_url}")
    click.echo(f"📺 B站视频模式: {'直接嵌入播放器' if bilibili_mode == 'iframe' else '生成跳转链接'}")
    
    if target_categories:
        click.echo(f"🎯 目标分类: {', '.join(target_categories)}")
    else:
        click.echo("🎯 抓取范围: 所有分类")
    
    click.echo("=" * 50)
    
    try:
        # 开始抓取
        if target_categories:
            result = scraper.scrape_categories(target_categories)
        else:
            result = scraper.scrape_all()
        
        # 显示结果
        click.echo()
        click.echo("🎉 抓取完成!")
        click.echo("=" * 50)
        click.echo(f"📊 总文章数: {result.total_articles}")
        click.echo(f"✅ 成功抓取: {result.successful_articles}")
        click.echo(f"❌ 失败数量: {result.failed_articles}")
        click.echo(f"📈 成功率: {result.get_success_rate():.1%}")
        click.echo(f"⏱️ 总耗时: {result.duration}")
        click.echo(f"📁 数据保存在: {output.absolute()}")
        
        # 显示分类统计
        if result.categories:
            click.echo()
            click.echo("📂 分类统计:")
            for category in result.categories:
                click.echo(f"  📁 {category.name}: {category.total_articles} 篇文章")
        
        click.echo("=" * 50)
        
    except KeyboardInterrupt:
        click.echo("\n⚠️ 用户中断抓取")
    except Exception as e:
        click.echo(f"\n❌ 抓取过程中出现错误: {e}", err=True)
        raise click.Abort()


@click.group()
def cli():
    """kintone开发者文档抓取器工具集"""
    pass


@cli.command()
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help='分析结果输出目录'
)
def analyze(output: Path):
    """分析网站结构，不下载内容"""
    click.echo("🔍 分析kintone网站结构...")
    
    scraper = KintoneScraper(output_dir=output)
    section_links = scraper._extract_section_links()
    
    click.echo(f"📊 发现 {len(section_links)} 个sections")
    
    categories_info = {}
    total_articles = 0
    
    for section_url in section_links:
        section = scraper._extract_section_info(section_url)
        if section:
            main_category = section.category_path.split('/')[0]
            if main_category not in categories_info:
                categories_info[main_category] = {'sections': 0, 'articles': 0}
            
            categories_info[main_category]['sections'] += 1
            categories_info[main_category]['articles'] += section.article_count
            total_articles += section.article_count
    
    click.echo()
    click.echo("📂 分类统计:")
    for category, info in categories_info.items():
        click.echo(f"  📁 {category}: {info['sections']} sections, {info['articles']} 篇文章")
    
    click.echo()
    click.echo(f"📈 总计: {total_articles} 篇文章")


@cli.command()
@click.argument('search_term')
@click.option(
    '--data-dir',
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help='数据目录路径'
)
def search(search_term: str, data_dir: Path):
    """在已抓取的文档中搜索"""
    click.echo(f"🔍 搜索: {search_term}")
    
    json_file = data_dir / "json" / "articles_index.json"
    if not json_file.exists():
        click.echo("❌ 未找到文章索引文件，请先运行抓取", err=True)
        return
    
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    results = []
    for article in articles:
        if search_term.lower() in article['title'].lower():
            results.append(article)
    
    if results:
        click.echo(f"📄 找到 {len(results)} 个结果:")
        for article in results:
            click.echo(f"  • {article['title']} ({article['category']})")
            click.echo(f"    {article['url']}")
            click.echo()
    else:
        click.echo("😕 未找到匹配的文章")


if __name__ == '__main__':
    main()

