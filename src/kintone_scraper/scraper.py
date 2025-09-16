"""核心抓取器"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import (
    BASE_URL, DEFAULT_HEADERS, DEFAULT_OUTPUT_DIR, MAIN_CATEGORIES,
    REQUEST_DELAY, REQUEST_TIMEOUT, SELECTORS, get_category_path, BILIBILI_VIDEO_MODE
)
from .models import Article, Category, ScrapingResult, Section
from .utils import (
    ProgressTracker, rate_limit, sanitize_filename, make_progress
)
from .image_downloader import ImageDownloader, HTMLGenerator
try:
    from .kf5_api import KF5HelpCenterClient  # optional API client
except Exception:
    KF5HelpCenterClient = None  # type: ignore


logger = logging.getLogger(__name__)


class KintoneScraper:
    """kintone文档抓取器"""
    
    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR, base_url: str = BASE_URL, enable_images: bool = True, try_external_images: bool = False, bilibili_mode: str = None, skip_existing: bool = True):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.enable_images = enable_images
        self.try_external_images = try_external_images
        self.bilibili_mode = bilibili_mode or BILIBILI_VIDEO_MODE
        self.skip_existing = skip_existing  # 是否跳过已存在的文章HTML
        
        # 创建session
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        
        # 跟踪已访问的URL
        self.visited_urls: Set[str] = set()
        
        # 抓取结果
        self.result = ScrapingResult()
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化图片下载器和HTML生成器
        if self.enable_images:
            self.image_downloader = ImageDownloader(self.base_url, self.output_dir, self.try_external_images, self.bilibili_mode)
            self.html_generator = HTMLGenerator(self.output_dir)
        else:
            self.image_downloader = None
            self.html_generator = None

        # 初始化可选的 KF5 API 客户端，用于富化元数据
        self.kf5 = None
        if KF5HelpCenterClient is not None:
            try:
                self.kf5 = KF5HelpCenterClient()
                logger.info("KF5 API 已启用用于元数据富化")
            except Exception as e:
                logger.warning(f"KF5 API 初始化失败，忽略 API 富化: {e}")
        
        # 设置日志
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """设置日志"""
        log_file = self.output_dir / "scraper.log"
        
        # 配置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 配置logger
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    def _extract_article_id(self, url: str) -> Optional[str]:
        """从文章URL中提取ID，如 /hc/kb/article/211164/ -> 211164"""
        try:
            import re
            m = re.search(r"/hc/kb/article/(\d+)/", url)
            return m.group(1) if m else None
        except Exception:
            return None

    def _existing_html_for_id(self, article_id: str) -> Optional[Path]:
        """检查是否已有该文章ID生成的HTML文件，返回路径或None"""
        try:
            html_root = self.output_dir / "html"
            if not html_root.exists():
                return None
            # 递归查找任意分类下以 ID_ 开头的文件
            for path in html_root.rglob(f"{article_id}_*.html"):
                if path.is_file():
                    return path
            return None
        except Exception:
            return None
    
    def _get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """获取页面内容"""
        if url in self.visited_urls:
            logger.debug(f"跳过已访问的URL: {url}")
            return None
        
        try:
            logger.info(f"访问: {url}")
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            self.visited_urls.add(url)
            return BeautifulSoup(response.text, 'html.parser')
            
        except requests.RequestException as e:
            logger.error(f"获取页面失败 {url}: {e}")
            return None
    
    def _extract_section_links(self) -> List[str]:
        """提取所有section链接（通过首页和各分类页）"""
        logger.info("开始提取section链接...")

        soup = self._get_page_content(self.base_url)
        if not soup:
            return []

        section_links: Set[str] = set()

        # 1) 从首页已展示的section的“查看全部文档”链接抓一遍（兼容旧逻辑）
        try:
            more_links = soup.select(SELECTORS['section_links'])
            for link in more_links:
                href = link.get('href')
                if href and '/hc/kb/section/' in href:
                    full_url = urljoin(self.base_url, href)
                    section_links.add(full_url)
        except Exception as e:
            logger.warning(f"首页提取section链接失败: {e}")

        # 2) 提取所有分类链接，再进入分类页提取该分类下的所有section
        try:
            category_links = soup.select(SELECTORS.get('category_links', 'a[href*="/hc/kb/category/"]'))
            category_urls = []
            for a in category_links:
                href = a.get('href')
                if href and '/hc/kb/category/' in href:
                    category_urls.append(urljoin(self.base_url, href))
            category_urls = list(dict.fromkeys(category_urls))  # 去重并保持顺序

            logger.info(f"发现 {len(category_urls)} 个主分类，逐一提取其Sections")
            for cat_url in category_urls:
                cat_soup = self._get_page_content(cat_url)
                if not cat_soup:
                    continue
                sec_as = cat_soup.select('a[href*="/hc/kb/section/"]')
                for a in sec_as:
                    href = a.get('href')
                    if href and '/hc/kb/section/' in href:
                        section_links.add(urljoin(self.base_url, href))
                rate_limit(REQUEST_DELAY)
        except Exception as e:
            logger.warning(f"分类页提取section链接失败: {e}")

        links = list(section_links)
        logger.info(f"共发现 {len(links)} 个section")
        return links
    
    def _extract_section_info(self, section_url: str) -> Optional[Section]:
        """提取section信息和文章列表"""
        soup = self._get_page_content(section_url)
        if not soup:
            return None
        
        # 获取section标题，优先从页面title中提取
        section_title = ""
        
        # 首先尝试从页面title中提取
        title_elem = soup.find('title')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            # 标题格式通常是 "Section名 - cybozu - cybozu开发者网站"
            parts = title_text.split(' - ')
            if len(parts) > 0:
                section_title = parts[0].strip()
        
        # 如果title提取失败，尝试其他选择器
        if not section_title:
            title_selectors = [
                'h1.section-title',
                '.section-header h1', 
                'h1',
                '.breadcrumb li:last-child'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    section_title = title_elem.get_text(strip=True)
                    if section_title:  # 确保不是空字符串
                        break
        
        # 获取描述
        description = ""
        desc_elem = soup.find('p', class_='section-description')
        if desc_elem:
            description = desc_elem.get_text(strip=True)
        
        # 提取文章链接
        article_links = []
        for link in soup.select(SELECTORS['article_links']):
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                article_links.append(full_url)
        
        # 获取分类路径：优先使用页面面包屑中的主分类/子分类
        category_path = ""
        try:
            breadcrumb = soup.select_one(SELECTORS.get('breadcrumbs', SELECTORS.get('breadcrumb', '')))
            if breadcrumb:
                # 面包屑通常类似： 首页 > 开发范例 > 自定义开发
                items = [li.get_text(strip=True) for li in breadcrumb.find_all('li')]
                if len(items) >= 3:
                    main_cat = items[1]
                    sub_cat = items[-1]
                    if main_cat and sub_cat:
                        category_path = f"{main_cat}/{sub_cat}"
        except Exception:
            pass

        # 回退到静态映射
        if not category_path:
            category_path = get_category_path(section_title)
        
        section = Section(
            url=section_url,
            title=section_title,
            description=description,
            articles=article_links,
            category_path=category_path
        )
        # article_count会在__post_init__中自动计算
        
        logger.info(f"Section: {section_title} - {len(article_links)} 篇文章 - 分类: {category_path}")
        return section
    
    def _extract_article_content(self, article_url: str, section: Section) -> Optional[Article]:
        """提取文章内容"""
        soup = self._get_page_content(article_url)
        if not soup:
            return None
        
        article = Article(url=article_url, section_title=section.title)
        
        try:
            # 首先尝试找到article标签
            article_elem = soup.select_one('article')
            if article_elem:
                # 在处理图片前，优先解析面包屑用于确定分类深度（影响图片相对路径）
                processing_category = section.category_path
                if not processing_category:
                    try:
                        breadcrumb = soup.select_one(SELECTORS.get('breadcrumbs', SELECTORS.get('breadcrumb', '')))
                        if breadcrumb:
                            links = breadcrumb.find_all('a')
                            texts = [a.get_text(strip=True) for a in links]
                            # 期望: [首页, 主分类]
                            if len(texts) >= 2:
                                main_cat = texts[-1] if len(texts) == 2 else texts[1]
                                # 最后一个 li 可能是纯文本子分类
                                last_li = breadcrumb.find_all('li')[-1]
                                sub_cat = last_li.get_text(strip=True) if last_li else ''
                                if main_cat and sub_cat:
                                    processing_category = f"{main_cat}/{sub_cat}"
                    except Exception:
                        pass
                # 从article内部提取标题
                title_elem = article_elem.find(['h1', 'h2', 'h3'])
                if title_elem:
                    article.title = title_elem.get_text(strip=True)
                # 若已解析出完整分类路径，直接赋给文章分类，确保保存目录正确
                if processing_category:
                    article.category = processing_category
                
                # 处理图片（如果启用）
                if self.enable_images and self.image_downloader:
                    # 处理HTML中的图片，下载并更新链接
                    processed_html, downloaded_images = self.image_downloader.process_html_images(
                        str(article_elem), article.title, article.url, processing_category or section.category_path, processing_category or section.category_path
                    )
                    article.html_content = processed_html
                    
                    # 记录下载的图片信息
                    if downloaded_images:
                        article.image_paths = downloaded_images  # 保存图片路径信息
                        logger.info(f"文章 '{article.title}' 下载了 {len(downloaded_images)} 张图片")
                else:
                    # 即使不处理图片，也需要处理链接
                    if self.image_downloader:
                        processed_html, _ = self.image_downloader.process_html_images(
                            str(article_elem), article.title, article.url, section.category_path, section.category_path
                        )
                        article.html_content = processed_html
                    else:
                        article.html_content = str(article_elem)
                
                # 清理文章内容，移除不需要的导航和互动元素
                article_copy = BeautifulSoup(article.html_content, 'html.parser')
                self._clean_article_content(article_copy)
                article.html_content = str(article_copy)
                
                # 移除脚本和样式，提取纯文本
                # 需要重新解析原始的article元素来获取纯文本，因为processed_html可能包含修改后的链接
                text_copy = BeautifulSoup(str(article_elem), 'html.parser')
                self._clean_article_content(text_copy)
                for script in text_copy.find_all(['script', 'style']):
                    script.decompose()
                
                # 提取纯文本
                article.content = text_copy.get_text(strip=True)
                # 重新计算内容长度
                article.content_length = len(article.content)
            else:
                # 如果没有article标签，使用原来的逻辑作为备用
                # 提取标题
                for selector in SELECTORS['title']:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        article.title = title_elem.get_text(strip=True)
                        break
                
                # 提取内容 - 使用备用选择器
                fallback_selectors = ['.article-content', '.kb-article-content', '.content-body', '.main-content']
                for selector in fallback_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        article.html_content = str(content_elem)
                        
                        # 移除脚本和样式
                        for script in content_elem.find_all(['script', 'style']):
                            script.decompose()
                        
                        article.content = content_elem.get_text(strip=True)
                        # 重新计算内容长度
                        article.content_length = len(article.content)
                        break
            
            # 提取分类信息（若上面未能通过processing_category设置）
            if not getattr(article, 'category', None):
                breadcrumb = soup.select_one(SELECTORS.get('breadcrumbs', SELECTORS.get('breadcrumb', '')))
                if breadcrumb:
                    # 期望： 首页 > 主分类 > 子分类
                    links = breadcrumb.find_all('a')
                    texts = [a.get_text(strip=True) for a in links]
                    if len(texts) >= 2:
                        main_cat = texts[-1] if len(texts) == 2 else texts[1]
                        last_li = breadcrumb.find_all('li')[-1]
                        sub_cat = last_li.get_text(strip=True) if last_li else ''
                        if main_cat and sub_cat:
                            article.category = f"{main_cat}/{sub_cat}"
            
            # 如果没有从面包屑获取到分类，使用section的分类
            if not article.category:
                article.category = section.category_path.split('/')[-1]
            
            # 提取更新时间
            time_elem = soup.select_one(SELECTORS['last_updated'])
            if time_elem:
                article.last_updated = time_elem.get('datetime') or time_elem.get_text(strip=True)
            
            if article.title:
                logger.debug(f"成功提取文章: {article.title}")
                return article
            else:
                logger.warning(f"文章无标题: {article_url}")
                return None
                
        except Exception as e:
            logger.error(f"提取文章内容失败 {article_url}: {e}")
            return None
    
    def _clean_article_content(self, soup: BeautifulSoup) -> None:
        """清理文章内容，移除导航和互动元素"""
        # 移除常见的导航和互动元素
        selectors_to_remove = [
            # 页面底部区域
            'footer',
            '.footer',
            
            # 上一篇/下一篇导航
            '.article-nav',
            '.article-navigation',
            '.prev-next',
            '.pagination',
            '[class*="prev"]',
            '[class*="next"]',
            
            # 评分和反馈
            '.rating',
            '.feedback',
            '.helpful',
            '.vote',
            '[class*="helpful"]',
            '[class*="vote"]',
            '[class*="rating"]',
            
            # 社交分享
            '.share',
            '.social',
            '[class*="share"]',
            '[class*="social"]',
            
            # 评论区
            '.comments',
            '.comment',
            '[class*="comment"]',
            
            # 其他常见的导航元素
            '.breadcrumb',
            '.sidebar',
            '.related',
            '.tags',
            '.category-nav'
        ]
        
        # 移除匹配的元素
        for selector in selectors_to_remove:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 移除包含特定文本的元素（更精确的清理）
        texts_to_remove = [
            '上一篇',
            '下一篇',
            '有帮助',
            '人觉得有帮助',
            '觉得有帮助',
            '分享',
            '收藏',
            '点赞',
            '评论',
            '相关文章'
        ]
        
        # 查找包含这些文本的元素并移除其父容器
        for text in texts_to_remove:
            # 查找包含特定文本的元素
            for elem in soup.find_all(text=lambda t: t and text in t):
                parent = elem.parent
                if parent and parent.name:
                    # 检查父元素是否应该被移除
                    parent_text = parent.get_text(strip=True)
                    if len(parent_text) < 200:  # 只移除短文本的容器，避免误删正文
                        logger.debug(f"移除导航元素: {parent_text[:50]}...")
                        parent.decompose()
                        break
    
    def _save_article_files(self, article: Article, section: Section) -> None:
        """保存文章文件"""
        if not article.title:
            return
        
        # 获取分类路径
        category_parts = section.category_path.split('/')
        
        # 生成HTML文件（如果启用图片功能）
        if self.enable_images and self.html_generator and article.html_content:
            try:
                # 设置文章的分类路径供HTML生成器使用
                article.category = section.category_path
                
                html_file = self.html_generator.generate_article_html(
                    article, 
                    article.html_content,
                    []  # 图片信息已经在html_content中更新了链接
                )
                
                if html_file:
                    logger.debug(f"HTML文件已生成: {html_file}")
                    
            except Exception as e:
                logger.error(f"生成HTML文件失败 {article.title}: {e}")
    
    def _organize_by_categories(self, sections: List[Section]) -> List[Category]:
        """按分类组织sections"""
        categories_dict: Dict[str, Category] = {}
        
        for section in sections:
            category_path = section.category_path
            main_category = category_path.split('/')[0]
            
            if main_category not in categories_dict:
                categories_dict[main_category] = Category(
                    name=main_category,
                    path=main_category
                )
            
            categories_dict[main_category].add_section(section)
        
        return list(categories_dict.values())
    
    def scrape_all(self) -> ScrapingResult:
        """抓取所有文档"""
        logger.info("="*60)
        logger.info("开始抓取kintone开发者文档")
        logger.info("="*60)
        
        try:
            # 1. 提取所有section链接
            section_links = self._extract_section_links()
            if not section_links:
                logger.error("未找到任何section链接")
                return self.result
            
            self.result.total_sections = len(section_links)
            
            # 2. 处理每个section
            sections: List[Section] = []
            section_progress = make_progress(len(section_links), "处理Sections:")
            
            for section_url in section_links:
                section = self._extract_section_info(section_url)
                if section:
                    sections.append(section)
                    self.result.total_articles += section.article_count
                
                section_progress.update()
                rate_limit(REQUEST_DELAY)
            
            section_progress.finish()
            
            # 3. 按分类组织
            self.result.categories = self._organize_by_categories(sections)
            
            # 4. 准备抓取
            
            # 5. 抓取所有文章
            logger.info(f"开始抓取 {self.result.total_articles} 篇文章...")
            article_progress = make_progress(self.result.total_articles, "抓取文章:")
            
            for section in sections:
                for article_url in section.articles:
                    # 增量：若文件已存在则跳过
                    if self.skip_existing:
                        aid = self._extract_article_id(article_url) or ""
                        if aid:
                            existed = self._existing_html_for_id(aid)
                            if existed:
                                logger.info(f"跳过已存在文章: {aid} -> {existed}")
                                self.result.successful_articles += 1  # 计入成功以便统计
                                article_progress.update()
                                rate_limit(REQUEST_DELAY)
                                continue
                    article = self._extract_article_content(article_url, section)
                    
                    if article:
                        self.result.add_article(article, success=True)
                        self._save_article_files(article, section)
                    else:
                        self.result.failed_articles += 1
                    
                    article_progress.update()
                    rate_limit(REQUEST_DELAY)
            
            article_progress.finish()
            
            # 6. 保存结果
            self._save_results()
            
            # 7. 标记完成
            self.result.mark_completed()
            
            logger.info("="*60)
            logger.info("抓取完成!")
            logger.info(f"成功抓取: {self.result.successful_articles}/{self.result.total_articles} 篇文章")
            logger.info(f"成功率: {self.result.get_success_rate():.1%}")
            logger.info(f"耗时: {self.result.duration}")
            logger.info("="*60)
            
            return self.result
        
        except KeyboardInterrupt:
            logger.warning("用户中断抓取")
            self._save_results()
            return self.result

    def scrape_all_via_api(self) -> ScrapingResult:
        """通过 KF5 API 列表驱动抓取（更不易漏）。"""
        logger.info("="*60)
        logger.info("开始通过 API 列表驱动抓取")
        logger.info("="*60)

        if not self.kf5:
            logger.error("KF5 API 未配置或初始化失败，无法使用 API 列表驱动")
            return self.result

        try:
            # 1. 首先构建分类映射
            logger.info("🗂️  构建分类映射...")
            forum_mapping = self.kf5.build_category_mapping()
            logger.info(f"📋 获取到 {len(forum_mapping)} 个分类映射")
            
            # 先分页拉取全部 posts 列表，优先使用 API 提供的文章 URL
            page = 1
            per_page = 100
            posts: List[dict] = []  # 保留 {id, url, title, forum_id, forum_name}
            while True:
                data = self.kf5.list_all_posts(page=page, per_page=per_page)
                items = data.get('posts') or data.get('data') or data.get('items') or []
                if not isinstance(items, list) or not items:
                    break
                for it in items:
                    aid = str(it.get('id') or it.get('post_id') or it.get('article_id') or '').strip()
                    url = (it.get('url') or '').strip()
                    title = (it.get('title') or '').strip()
                    forum_id = it.get('forum_id')
                    forum_name = it.get('forum_name', '')
                    
                    # 容错策略：优先使用ID构造 KB URL；若URL已给出但非KB且有ID，也回退为KB URL
                    if not url and aid:
                        url = f"/hc/kb/article/{aid}/"
                    elif url and '/hc/kb/article/' not in url and aid:
                        url = f"/hc/kb/article/{aid}/"
                    # 仅当至少有 id 或 url 时加入
                    if aid or url:
                        posts.append({
                            'id': aid, 
                            'url': url, 
                            'title': title,
                            'forum_id': forum_id,
                            'forum_name': forum_name
                        })
                if len(items) < per_page:
                    break
                page += 1

            self.result.total_articles = len(posts)
            logger.info(f"API 返回可能的KB文章: {len(posts)}")

            # 逐篇抓取 HTML 页面，使用正确的分类信息
            from .models import Section

            article_progress = make_progress(self.result.total_articles or 1, "抓取文章:")
            for p in posts:
                article_url = urljoin(self.base_url, p.get('url') or f"/hc/kb/article/{p.get('id')}/")
                
                # 为每篇文章创建带有正确分类的section
                forum_id = p.get('forum_id')
                category_path = "其他/未知"  # 默认值
                
                if forum_id and forum_id in forum_mapping:
                    category_path = forum_mapping[forum_id]['full_path']
                elif p.get('forum_name'):
                    category_path = f"其他/{p.get('forum_name')}"
                
                article_section = Section(
                    url="", 
                    title=p.get('forum_name', '未知分类'), 
                    description="", 
                    articles=[], 
                    category_path=category_path
                )
                
                # 增量：若文件已存在则跳过
                if self.skip_existing:
                    pid = str(p.get('id') or '').strip()
                    if pid:
                        existed = self._existing_html_for_id(pid)
                        if existed:
                            logger.info(f"跳过已存在文章: {pid} -> {existed}")
                            self.result.successful_articles += 1
                            article_progress.update()
                            rate_limit(REQUEST_DELAY)
                            continue
                
                article = self._extract_article_content(article_url, article_section)
                if article:
                    self.result.add_article(article, success=True)
                    self._save_article_files(article, article_section)
                else:
                    self.result.failed_articles += 1
                article_progress.update()
                rate_limit(REQUEST_DELAY)
            article_progress.finish()

            # 保存结果并标记
            self._save_results()
            self.result.mark_completed()
            logger.info("抓取完成(基于API列表)")
            logger.info(f"成功抓取: {self.result.successful_articles}/{self.result.total_articles}")
            return self.result

        except KeyboardInterrupt:
            logger.warning("用户中断抓取")
            self._save_results()
            return self.result
        except Exception as e:
            logger.error(f"抓取过程中出现错误: {e}")
            self._save_results()
            return self.result
    
    def scrape_categories(self, category_names: List[str]) -> ScrapingResult:
        """只抓取指定分类的文档"""
        logger.info(f"开始抓取指定分类: {category_names}")
        
        # 获取所有section链接
        section_links = self._extract_section_links()
        
        # 过滤出指定分类的sections
        filtered_sections = []
        for section_url in section_links:
            section = self._extract_section_info(section_url)
            if section:
                main_category = section.category_path.split('/')[0]
                if main_category in category_names:
                    filtered_sections.append(section)
        
        logger.info(f"找到 {len(filtered_sections)} 个匹配的sections")
        
        # 使用过滤后的sections继续抓取
        # ... (类似scrape_all的逻辑)
        
        return self.result
    
    def _save_results(self) -> None:
        """保存抓取结果"""
        logger.info("保存抓取结果...")

        # 生成HTML索引页面（如果启用）
        if self.enable_images and self.html_generator:
            try:
                index_file = self.html_generator.generate_index_html(
                    self.result.categories,
                    self.result.articles
                )
                logger.info(f"HTML索引页面已生成: {index_file}")
            except Exception as e:
                logger.error(f"生成HTML索引页面失败: {e}")

        # 保存图片下载统计（如果启用）
        if self.enable_images and self.image_downloader:
            image_stats = self.image_downloader.get_download_stats()
            logger.info(f"图片下载统计: 成功 {image_stats['images_downloaded']}, 失败 {image_stats['failed']}")
            if image_stats.get('attachments_downloaded', 0) > 0:
                logger.info(f"附件下载统计: 成功 {image_stats['attachments_downloaded']}")

        logger.info("结果保存完成")
    
    def _generate_report(self) -> None:
        """生成抓取报告"""
        report_file = self.output_dir / "scraping_report.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# kintone开发者文档抓取报告\n\n")
            f.write(f"**抓取时间**: {self.result.start_time}\n")
            f.write(f"**完成时间**: {self.result.end_time}\n")
            f.write(f"**总耗时**: {self.result.duration}\n\n")
            
            f.write("## 📊 统计概览\n\n")
            f.write(f"- **总Section数**: {self.result.total_sections}\n")
            f.write(f"- **总文章数**: {self.result.total_articles}\n")
            f.write(f"- **成功抓取**: {self.result.successful_articles}\n")
            f.write(f"- **失败数量**: {self.result.failed_articles}\n")
            f.write(f"- **成功率**: {self.result.get_success_rate():.1%}\n\n")
            
            f.write("## 📂 分类统计\n\n")
            for category in self.result.categories:
                f.write(f"### {category.name}\n")
                f.write(f"- **总文章数**: {category.total_articles}\n")
                f.write(f"- **Sections**: {len(category.sections)}\n\n")
                
                for section in category.sections:
                    f.write(f"  - **{section.title}**: {section.article_count} 篇文章\n")
                f.write("\n")
        
        logger.info(f"报告已生成: {report_file}")
