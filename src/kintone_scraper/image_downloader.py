"""图片下载器模块"""

import hashlib
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import (
    DEFAULT_HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT,
    get_article_file_path, calculate_relative_path, BILIBILI_VIDEO_MODE
)
from .utils import get_safe_filename, rate_limit

logger = logging.getLogger(__name__)


class ImageDownloader:
    """图片下载器"""
    
    def __init__(self, base_url: str, output_dir: Path, try_external_images: bool = False, bilibili_mode: str = None):
        self.base_url = base_url
        self.output_dir = output_dir
        self.try_external_images = try_external_images  # 是否尝试下载外部图片
        self.bilibili_mode = bilibili_mode or BILIBILI_VIDEO_MODE  # B站视频处理模式
        self.images_dir = output_dir / "images"
        self.attachments_dir = output_dir / "attachments"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

        # 创建session
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        # 跟踪已下载的图片和附件
        self.downloaded_images: Dict[str, str] = {}  # URL -> 本地文件名
        self.downloaded_attachments: Dict[str, str] = {}  # URL -> 本地文件名
        self.failed_downloads: Set[str] = set()
        
        # 强制清理任何可能的缓存状态
        self._reset_download_state()

        # 支持的图片格式
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
        
        # 支持的附件格式
        self.attachment_formats = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                                 '.zip', '.rar', '.7z', '.txt', '.csv', '.json', '.xml'}
    
    def _reset_download_state(self):
        """重置下载状态，清理所有缓存"""
        self.downloaded_images.clear()
        self.downloaded_attachments.clear()
        self.failed_downloads.clear()
        logger.debug("下载状态已重置")
    
    def _get_image_extension(self, url: str, content_type: str = None, content_preview: bytes = None) -> str:
        """获取图片文件扩展名"""
        # 首先尝试从URL获取扩展名
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        for ext in self.supported_formats:
            if path.endswith(ext):
                return ext
        
        # 尝试从文件内容的魔术字节判断格式
        if content_preview:
            if content_preview.startswith(b'\xFF\xD8\xFF'):
                return '.jpg'
            elif content_preview.startswith(b'\x89PNG\r\n\x1a\n'):
                return '.png'
            elif content_preview.startswith(b'GIF8'):
                return '.gif'
            elif content_preview.startswith(b'\x42\x4D'):
                return '.bmp'
            elif content_preview.startswith(b'RIFF') and b'WEBP' in content_preview[:20]:
                return '.webp'
        
        # 如果URL没有扩展名，尝试从Content-Type获取
        if content_type:
            ext = mimetypes.guess_extension(content_type.split(';')[0])
            if ext and ext.lower() in self.supported_formats:
                return ext.lower()
        
        # 默认使用.jpg
        return '.jpg'
    
    def _generate_filename(self, url: str, content_type: str = None, content_preview: bytes = None) -> str:
        """生成安全的文件名"""
        # 使用URL的hash作为文件名，避免重复和特殊字符问题
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
        
        # 获取扩展名
        extension = self._get_image_extension(url, content_type, content_preview)
        
        return f"{url_hash}{extension}"
    
    def _is_external_image_host(self, url: str) -> bool:
        """检查图片URL是否来自外部图床"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # 已知的外部图床域名
            external_hosts = {
                's3.bmp.ovh',
                'imgchr.com',
                'imgtu.com',
                'sm.ms',
                'imgur.com',
                'githubusercontent.com',
                'raw.githubusercontent.com',
                'cloudflare-ipfs.com',
                'ipfs.io',
                'pinata.cloud',
                'arweave.net',
                'nft.storage',
                'web3.storage',
                'infura-ipfs.io'
            }

            # 检查是否是已知的外部图床
            if any(host in domain for host in external_hosts):
                return True

            # 检查是否是当前网站的子域名以外的其他域名
            base_domain = urlparse(self.base_url).netloc.lower()
            if parsed.netloc and parsed.netloc != base_domain:
                # 检查是否是同一主域名的不同子域名
                # 例如：files.kf5.com 和 cybozudev.kf5.com 都属于 kf5.com
                def get_main_domain(domain):
                    parts = domain.split('.')
                    if len(parts) >= 2:
                        return '.'.join(parts[-2:])  # 取最后两部分作为主域名
                    return domain
                
                main_domain = get_main_domain(base_domain)
                image_main_domain = get_main_domain(domain)
                
                # 如果不是同一主域名，则认为是外部图床
                if image_main_domain != main_domain:
                    return True

            return False
        except Exception:
            return False

    def _is_valid_image_url(self, url: str) -> bool:
        """检查是否是有效的图片URL"""
        if not url:
            return False

        # 检查URL格式
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
        except Exception:
            return False

        # 检查是否是支持的图片格式
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in self.supported_formats):
            return True

        # 对于没有明确扩展名的URL，也尝试下载
        return True
    
    def download_image(self, image_url: str) -> Optional[str]:
        """下载单个图片，返回本地文件名"""
        if not self._is_valid_image_url(image_url):
            logger.debug(f"跳过无效图片URL: {image_url}")
            return None

        # 转换为绝对URL
        absolute_url = urljoin(self.base_url, image_url)

        # 检查是否是外部图床
        is_external = self._is_external_image_host(absolute_url)
        if is_external and not self.try_external_images:
            logger.debug(f"跳过外部图床图片: {absolute_url}")
            return None
        elif is_external:
            logger.info(f"尝试下载外部图床图片: {absolute_url}")
        else:
            logger.debug(f"下载同域图片: {absolute_url}")

        # 检查是否已经下载过
        if absolute_url in self.downloaded_images:
            cached_filename = self.downloaded_images[absolute_url]
            logger.debug(f"使用缓存的图片: {absolute_url} -> {cached_filename}")
            return cached_filename

        # 检查是否下载失败过
        if absolute_url in self.failed_downloads:
            logger.debug(f"跳过已知失败的图片: {absolute_url}")
            return None
        
        # 尝试下载图片（不重试，避免浪费时间）
        max_retries = 0
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"下载图片: {absolute_url}")
                
                # 为外部图床设置更好的请求头
                if is_external:
                    logger.debug(f"检测到外部图床: {absolute_url}")
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'image',
                        'Sec-Fetch-Mode': 'no-cors',
                        'Sec-Fetch-Site': 'cross-site',
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache',
                    }
                    
                    # 创建新的session来避免cookie干扰
                    external_session = requests.Session()
                    external_session.headers.update(headers)
                    
                    # 对于某些特殊域名，调整请求头
                    if 's3.bmp.ovh' in absolute_url:
                        headers['Referer'] = 'https://bmp.ovh/'
                        headers['Origin'] = 'https://bmp.ovh'
                        external_session.headers.update(headers)
                        logger.debug(f"为s3.bmp.ovh设置特殊请求头")
                    
                    response = external_session.get(absolute_url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)
                    logger.debug(f"外部图片请求完成，状态码: {response.status_code}")
                else:
                    # 使用session下载同域图片
                    response = self.session.get(absolute_url, timeout=REQUEST_TIMEOUT, stream=True)
                    logger.debug(f"内部图片请求完成，状态码: {response.status_code}")
                
                response.raise_for_status()
                logger.debug(f"图片请求成功: {absolute_url}")
                
                # 检查Content-Type和URL扩展名
                content_type = response.headers.get('content-type', '')
                
                # 从URL获取可能的扩展名
                parsed_url = urlparse(absolute_url)
                url_path = parsed_url.path.lower()
                has_image_extension = any(url_path.endswith(ext) for ext in self.supported_formats)
                
                # 检查是否是图片：Content-Type是image/*，或者URL有图片扩展名，或者是kf5.com的附件链接，或者是外部图床
                is_image_content_type = content_type.startswith('image/')
                is_kf5_attachment = 'files.kf5.com' in absolute_url or 'attachments/download' in absolute_url
                
                # 对于外部图床，更宽松的验证 - 只要URL看起来像图片就尝试下载
                if not (is_image_content_type or has_image_extension or is_kf5_attachment or is_external):
                    logger.warning(f"URL不是图片: {absolute_url} (Content-Type: {content_type}, 路径: {url_path})")
                    self.failed_downloads.add(absolute_url)
                    return None
                
                # 如果是外部图床但Content-Type不是image/*，记录但继续尝试
                if is_external and not is_image_content_type:
                    logger.debug(f"外部图床Content-Type不是image/*，但仍尝试下载: {absolute_url} (Content-Type: {content_type})")
                
                # 对于kf5.com的文件，即使Content-Type不是image/*，也尝试下载
                if is_kf5_attachment and not is_image_content_type:
                    logger.info(f"尝试下载kf5.com附件作为图片: {absolute_url} (Content-Type: {content_type})")
                
                # 读取前几个字节来判断文件类型
                content_preview = None
                first_chunk = None
                content_chunks = []
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        content_chunks.append(chunk)
                        if first_chunk is None:
                            first_chunk = chunk
                            content_preview = chunk[:20]  # 读取前20字节用于格式判断
                        
                            # 如果不是明确的图片Content-Type，通过文件头判断是否是图片
                            if not is_image_content_type:
                                is_image_by_header = (content_preview.startswith(b'\xFF\xD8\xFF') or  # JPEG
                                                    content_preview.startswith(b'\x89PNG\r\n\x1a\n') or  # PNG
                                                    content_preview.startswith(b'GIF8') or  # GIF
                                                    content_preview.startswith(b'\x42\x4D') or  # BMP
                                                    (content_preview.startswith(b'RIFF') and b'WEBP' in content_preview))  # WEBP
                                
                                if not is_image_by_header:
                                    # 对于外部图床，即使文件头不匹配也尝试保存（可能是特殊格式或压缩）
                                    if is_external:
                                        logger.warning(f"外部图床文件头不匹配，但仍尝试保存: {absolute_url} (文件头: {content_preview[:10].hex()})")
                                    else:
                                        logger.warning(f"文件不是图片格式: {absolute_url} (文件头: {content_preview[:10].hex()})")
                                        self.failed_downloads.add(absolute_url)
                                        return None
                                else:
                                    logger.info(f"通过文件头确认为图片: {absolute_url}")
                
                # 生成文件名（使用内容预览来更准确地判断扩展名）
                filename = self._generate_filename(absolute_url, content_type, content_preview)
                filepath = self.images_dir / filename
                
                # 保存图片
                with open(filepath, 'wb') as f:
                    for chunk in content_chunks:
                        f.write(chunk)
                
                logger.debug(f"图片保存成功: {filename}")
                self.downloaded_images[absolute_url] = filename
                
                # 控制下载速度
                rate_limit(REQUEST_DELAY * 0.5)  # 图片下载稍快一些
                
                return filename
                
            except (requests.RequestException, Exception) as e:
                # 不重试，直接记录失败
                logger.error(f"图片下载失败: {absolute_url} - {str(e)}")
                self.failed_downloads.add(absolute_url)
                return None

    def _extract_github_url_from_license(self, license_url: str, link_text: str) -> Optional[str]:
        """从license文件链接中提取GitHub项目URL"""
        try:
            # 常见的GitHub项目名称模式
            import re
            
            # 从链接文本中提取可能的项目名称
            # 例如: "MIT-LICENSE_115.txt" -> 可能是某个项目的license
            # 或者链接文本本身就包含项目名称
            
            # 一些已知的项目映射（可以根据实际情况扩展）
            project_mappings = {
                'express': 'https://github.com/expressjs/express',
                'react': 'https://github.com/facebook/react',
                'vue': 'https://github.com/vuejs/vue',
                'angular': 'https://github.com/angular/angular',
                'jquery': 'https://github.com/jquery/jquery',
                'bootstrap': 'https://github.com/twbs/bootstrap',
                'lodash': 'https://github.com/lodash/lodash',
                'moment': 'https://github.com/moment/moment',
                'axios': 'https://github.com/axios/axios',
                'webpack': 'https://github.com/webpack/webpack',
                'babel': 'https://github.com/babel/babel',
                'eslint': 'https://github.com/eslint/eslint',
                'typescript': 'https://github.com/microsoft/TypeScript',
                'node': 'https://github.com/nodejs/node',
                'npm': 'https://github.com/npm/npm',
            }
            
            # 检查链接文本或URL中是否包含已知项目名称
            text_lower = link_text.lower()
            url_lower = license_url.lower()
            
            for project_name, github_url in project_mappings.items():
                if project_name in text_lower or project_name in url_lower:
                    logger.debug(f"找到匹配的项目: {project_name} -> {github_url}")
                    return github_url
            
            # 如果无法匹配到具体项目，返回None
            logger.debug(f"无法确定license文件对应的GitHub项目: {license_url}")
            return None
            
        except Exception as e:
            logger.warning(f"提取GitHub URL时出错: {e}")
            return None

    def download_attachment(self, attachment_url: str) -> Optional[str]:
        """下载附件，返回本地文件名"""
        if not attachment_url:
            return None

        # 转换为绝对URL
        absolute_url = urljoin(self.base_url, attachment_url)
        
        # 检查是否已经下载过
        if absolute_url in self.downloaded_attachments:
            return self.downloaded_attachments[absolute_url]

        # 检查是否下载失败过
        if absolute_url in self.failed_downloads:
            return None
        
        try:
            logger.info(f"下载附件: {absolute_url}")
            
            # 下载附件
            response = self.session.get(absolute_url, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            
            # 生成基于URL的唯一文件名，避免重复下载相同文件
            import hashlib
            url_hash = hashlib.md5(absolute_url.encode()).hexdigest()[:8]
            
            # 尝试从响应头获取原始文件名
            content_disposition = response.headers.get('content-disposition', '')
            original_filename = None
            
            if content_disposition:
                import re
                # 支持RFC 5987格式：filename*=UTF-8''filename
                rfc5987_match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
                if rfc5987_match:
                    from urllib.parse import unquote
                    original_filename = unquote(rfc5987_match.group(1))
                    logger.debug(f"从RFC5987格式解析文件名: {original_filename}")
                else:
                    # 传统格式：filename="filename" 或 filename=filename
                    traditional_match = re.search(r'filename[*]?=([^;]+)', content_disposition)
                    if traditional_match:
                        original_filename = traditional_match.group(1).strip('"\'')
                        logger.debug(f"从传统格式解析文件名: {original_filename}")
            
            # 如果无法从响应头获取文件名，从URL解析
            if not original_filename:
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(absolute_url)
                path_parts = parsed_url.path.split('/')
                
                # 寻找可能的文件名
                for part in reversed(path_parts):
                    if part and '.' in part:
                        original_filename = unquote(part)
                        logger.debug(f"从URL路径解析文件名: {original_filename}")
                        break
            
            # 生成最终文件名：hash_原始名称 或 hash.扩展名
            if original_filename:
                # 清理原始文件名
                clean_original = get_safe_filename(original_filename, max_length=50)
                filename = f"{url_hash}_{clean_original}"
            else:
                # 根据Content-Type生成扩展名
                content_type = response.headers.get('content-type', '').lower()
                
                if 'pdf' in content_type:
                    filename = f"{url_hash}.pdf"
                elif 'zip' in content_type or 'compressed' in content_type:
                    filename = f"{url_hash}.zip"
                elif 'word' in content_type or 'msword' in content_type:
                    filename = f"{url_hash}.doc"
                elif 'excel' in content_type or 'spreadsheet' in content_type:
                    filename = f"{url_hash}.xlsx"
                elif 'json' in content_type:
                    filename = f"{url_hash}.json"
                elif 'text' in content_type:
                    filename = f"{url_hash}.txt"
                else:
                    filename = f"{url_hash}.bin"
                    
                logger.debug(f"根据Content-Type生成文件名: {filename} (Content-Type: {content_type})")
            
            # 确保文件名安全
            filename = get_safe_filename(filename)
            filepath = self.attachments_dir / filename
            
            # 避免文件名冲突
            counter = 1
            original_filepath = filepath
            while filepath.exists():
                name_part = original_filepath.stem
                ext_part = original_filepath.suffix
                filepath = self.attachments_dir / f"{name_part}_{counter}{ext_part}"
                counter += 1
            
            # 保存附件
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.debug(f"附件保存成功: {filepath.name}")
            self.downloaded_attachments[absolute_url] = filepath.name
            
            # 控制下载速度
            rate_limit(REQUEST_DELAY)
            
            return filepath.name
            
        except requests.RequestException as e:
            logger.error(f"下载附件失败 {absolute_url}: {e}")
            self.failed_downloads.add(absolute_url)
            return None
        except Exception as e:
            logger.error(f"保存附件失败 {absolute_url}: {e}")
            self.failed_downloads.add(absolute_url)
            return None
    
    def process_html_images(self, html_content: str, article_title: str = "", article_url: str = "", article_category: str = "", current_section_category: str = "") -> Tuple[str, List[str]]:
        """
        处理HTML中的图片和链接
        - 下载图片并替换为本地路径
        - 将有效超链接转换为span标签，保留原始信息
        - 将同一网站的文章链接转换为本地文件链接
        - 对于无效链接（如javascript:;），直接移除链接保留纯文本
        返回: (更新后的HTML, 下载的图片文件名列表)
        """
        if not html_content:
            return html_content, []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        downloaded_files = []

        # 由于HTML使用了base标签指向output根目录，
        # 图片路径应该直接基于output目录，不需要../前缀
        images_relative_path = "images"

        # 辅助函数：将同站点文章链接转换为本地链接
        def convert_to_local_link(href: str) -> Optional[tuple]:
            """将同一网站的文章链接转换为文章ID和链接类型
            
            Returns:
                tuple: (link_type, article_id_or_anchor)
                - ('anchor', anchor): 页面内锚点
                - ('article', article_id): 外部文章链接
                - None: 无效链接
            """
            logger.debug(f"检查链接转换: {href} (当前文章: {article_url})")

            if not href or not article_url:
                logger.debug("链接或文章URL为空，跳过转换")
                return None

            # 检查是否是同一网站的链接（包括相对路径）
            is_same_site = (
                'cybozudev.kf5.com' in href or  # 完整URL
                href.startswith('/hc/kb/article/') or  # 相对路径的文章链接
                href.startswith('../') or  # 相对路径
                (href.startswith('/') and 'hc/kb' in href)  # 其他相对路径
            )
            
            if not is_same_site:
                logger.debug(f"不是同一网站的链接，跳过转换: {href}")
                return None

            # 提取文章ID
            import re
            article_match = re.search(r'/hc/kb/article/(\d+)', href)
            if not article_match:
                logger.debug(f"未找到文章ID，跳过转换: {href}")
                return None

            target_article_id = article_match.group(1)
            logger.debug(f"提取到文章ID: {target_article_id}")

            # 检查是否是当前文章的锚点链接
            if f'/hc/kb/article/{target_article_id}' in article_url:
                # 这是指向当前文章的链接
                if '#' in href:
                    # 当前文章的锚点链接，返回锚点（稍后会转换为粗体）
                    anchor_match = re.search(r'#(.+)$', href)
                    if anchor_match:
                        logger.debug(f"转换为内部锚点: #{anchor_match.group(1)}")
                        return ('anchor', anchor_match.group(1))
                # 当前文章的链接但没有锚点，忽略
                logger.debug(f"忽略指向当前文章的链接: {href}")
                return None

            # 返回外部文章ID
            logger.debug(f"转换为外部文章链接: {href} -> 文章ID: {target_article_id}")
            return ('article', target_article_id)

        
        # 0. 处理iframe（特别是B站视频）
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if 'bilibili.com' in src or 'player.bilibili.com' in src:
                # 提取视频信息
                import re
                bv_match = re.search(r'bvid=([^&]+)', src)
                aid_match = re.search(r'aid=(\d+)', src)
                
                if bv_match or aid_match:
                    # 根据配置模式处理B站视频
                    if bv_match:
                        video_id = bv_match.group(1)
                        aid = aid_match.group(1) if aid_match else None
                        video_info = video_id
                    else:
                        aid = aid_match.group(1)
                        video_id = None
                        video_info = f"av{aid}"
                    
                    # 构建视频URL
                    if video_id:
                        video_url = f"https://www.bilibili.com/video/{video_id}"
                    else:
                        video_url = f"https://www.bilibili.com/video/av{aid}"
                    
                    # 创建友好的B站视频链接
                    container = soup.new_tag('div')
                    container['class'] = 'bilibili-video-link'
                    container['style'] = 'margin: 16px 0; padding: 16px; border: 2px solid #00a1d6; border-radius: 8px; background-color: #f0f8ff; text-align: center;'
                    
                    # 视频图标和标题
                    title_p = soup.new_tag('p')
                    title_p['style'] = 'margin: 0 0 8px 0; font-size: 16px; font-weight: bold; color: #333;'
                    title_p.string = f"📺 B站视频: {video_info}"
                    
                    # 提示文字和链接
                    link_p = soup.new_tag('p')
                    link_p['style'] = 'margin: 8px 0 0 0; font-size: 14px; color: #666;'
                    
                    hint_text = soup.new_tag('span')
                    hint_text.string = "请前往B站观看：  "
                    
                    a_tag = soup.new_tag('a')
                    a_tag.string = f"点击观看 {video_info} →"
                    a_tag['href'] = video_url
                    a_tag['target'] = "_blank"
                    a_tag['rel'] = "noopener noreferrer"
                    a_tag['class'] = "bilibili-link"
                    a_tag['style'] = "color: #00a1d6; text-decoration: none; font-weight: bold; font-size: 15px; padding: 4px 8px; border-radius: 4px; background-color: rgba(0, 161, 214, 0.1);"
                    
                    link_p.append(hint_text)
                    link_p.append(a_tag)
                    
                    container.append(title_p)
                    container.append(link_p)
                    
                    iframe.replace_with(container)
                    logger.debug(f"替换B站iframe为友好链接: {video_info} -> {video_url}")

        # 1. 处理图片
        img_tags = soup.find_all('img')
        
        if img_tags:
            # 统计不同的图片URL
            unique_urls = set()
            for img in img_tags:
                src = img.get('src')
                if src:
                    unique_urls.add(src)
            
            logger.info(f"文章 '{article_title}' 中发现 {len(img_tags)} 个img标签，{len(unique_urls)} 个不同图片")
            
            for img in img_tags:
                src = img.get('src')
                if not src:
                    continue

                # 下载图片
                filename = self.download_image(src)
                logger.debug(f"图片下载结果: {src} -> {filename}")
                
                # 如果下载失败但图片已在缓存中，使用缓存的文件名（容错处理）
                if not filename:
                    absolute_url = urljoin(self.base_url, src)
                    if absolute_url in self.downloaded_images:
                        filename = self.downloaded_images[absolute_url]
                        logger.debug(f"使用缓存的图片文件名: {src} -> {filename}")

                if filename:
                    # 更新img标签的src属性为相对路径
                    img['src'] = f"{images_relative_path}/{filename}"
                    # 只在首次成功下载时记录
                    if filename not in downloaded_files:
                        downloaded_files.append(filename)
                    logger.debug(f"图片链接已更新: {src} -> {images_relative_path}/{filename}")
                else:
                    # 图片下载失败，替换为文本提示
                    absolute_url = urljoin(self.base_url, src)
                    alt_text = img.get('alt', '图片')
                    
                    logger.warning(f"图片下载失败: {src}")
                    # 创建失败提示，区分外部和内部图片
                    if self._is_external_image_host(absolute_url):
                        placeholder = soup.new_tag('div')
                        placeholder['class'] = 'external-image-placeholder'
                        placeholder['style'] = 'border: 2px dashed #ffa500; padding: 20px; text-align: center; color: #ff8c00; background-color: #fff8e1; border-radius: 4px; margin: 10px 0;'
                        placeholder.string = f"🌐 外部图片下载失败: {alt_text}"
                    else:
                        placeholder = soup.new_tag('div')
                        placeholder['class'] = 'failed-image-placeholder'
                        placeholder['style'] = 'border: 2px dashed #ff6b6b; padding: 20px; text-align: center; color: #c92a2a; background-color: #ffe0e0; border-radius: 4px; margin: 10px 0;'
                        placeholder.string = f"❌ 图片下载失败: {alt_text}"
                    
                    # 替换img标签
                    img.replace_with(placeholder)
        else:
            logger.debug(f"文章 '{article_title}' 中没有找到图片")
        
        # 2. 处理超链接 - 转换为span标签或直接移除无效链接
        link_tags = soup.find_all('a')
        if link_tags:
            logger.info(f"文章 '{article_title}' 中发现 {len(link_tags)} 个链接，进行处理")

            for link in link_tags:
                href = link.get('href', '').strip()
                link_text = link.get_text(strip=True)

                if not link_text:
                    # 对于没有文本的链接，直接移除
                    link.decompose()
                    continue

                # 检查是否是无效链接
                invalid_hrefs = [
                    'javascript:;',
                    'javascript:void(0)',
                    'javascript:void(0);',
                    '#',
                    '',
                    None
                ]

                is_invalid_link = (
                    href.lower() in invalid_hrefs or
                    href.startswith('javascript:') or
                    href == '#'
                )

                if is_invalid_link:
                    # 对于无效链接，转换为span元素以保持样式和间距
                    span = soup.new_tag('span')
                    span.string = link_text
                    
                    # 复制原有的class属性（如果有的话）
                    if link.get('class'):
                        span['class'] = link.get('class')
                    
                    # 添加一个标识class
                    existing_classes = span.get('class', [])
                    if isinstance(existing_classes, str):
                        existing_classes = [existing_classes]
                    existing_classes.append('inactive-link')
                    span['class'] = existing_classes
                    
                    # 替换原来的a标签
                    link.replace_with(span)
                    logger.debug(f"将无效链接 '{href}' 转换为span: {link_text}")
                else:
                    # 尝试转换为本地链接
                    link_result = convert_to_local_link(href)

                    if link_result:
                        link_type, link_data = link_result
                        
                        if link_type == 'anchor':
                            # 页面内锚点链接 - 保留原样以支持页面内导航
                            a_tag = soup.new_tag('a')
                            a_tag.string = link_text
                            a_tag['href'] = link_data  # link_data是锚点ID
                        elif link_type == 'article':
                            # 同站点文章链接，使用文章ID引用格式（避免破坏SPA样式）
                            a_tag = soup.new_tag('a')
                            a_tag.string = link_text
                            a_tag['href'] = '#'  # 不直接跳转
                            a_tag['data-article-id'] = link_data  # link_data是文章ID
                            a_tag['data-original-href'] = href
                            a_tag['class'] = 'article-link'  # 用于前端JavaScript识别

                        # 替换原来的a标签
                        link.replace_with(a_tag)
                        logger.debug(f"转换为链接: {href} -> {link_type}:{link_data}")
                    elif href.startswith('#') and len(href) > 1:
                        # 页面内锚点链接 - 保留原样以支持页面内导航
                        logger.debug(f"保留锚点链接: {href}")
                        # 不做任何修改，保持原有的锚点链接
                    else:
                        # 检查是否是license文件链接 - 应该转换为GitHub项目链接
                        is_license_file = (
                            'license' in href.lower() and 
                            ('.txt' in href.lower() or '.md' in href.lower()) and
                            ('attachments/download' in href or 'files.kf5.com' in href)
                        )
                        
                        if is_license_file:
                            # license文件转换为GitHub项目链接的占位符
                            logger.debug(f"检测到license文件链接，转换为GitHub项目链接: {href}")
                            
                            # 尝试从链接文本中提取项目信息
                            github_url = self._extract_github_url_from_license(href, link_text)
                            
                            if github_url:
                                # 创建指向GitHub项目的外部链接
                                link['href'] = github_url
                                link['class'] = 'external-link'
                                link['target'] = '_blank'
                                link['rel'] = 'noopener noreferrer'
                                # 更新链接文本，添加GitHub图标
                                link.string = f"🔗 {link_text} (GitHub项目)"
                                logger.debug(f"license文件转换为GitHub链接: {href} -> {github_url}")
                            else:
                                # 无法确定GitHub项目，转换为纯文本
                                span = soup.new_tag('span')
                                span.string = f"📄 {link_text} (项目许可证)"
                                span['class'] = 'license-text'
                                span['style'] = 'color: #6b7280; font-weight: normal;'
                                link.replace_with(span)
                                logger.debug(f"license文件转换为纯文本: {href}")
                        else:
                            # 检查是否是其他附件下载链接
                            is_attachment = (
                                'attachments/download' in href or
                                'files.kf5.com/attachments' in href or
                                any(href.lower().endswith(ext) for ext in self.attachment_formats)
                            )
                            
                            if is_attachment:
                                # 尝试下载附件
                                attachment_filename = self.download_attachment(href)
                                
                                if attachment_filename:
                                    # 由于HTML使用了base标签指向output根目录，
                                    # 附件路径应该直接基于output目录，不需要../前缀
                                    local_attachment_path = f"attachments/{attachment_filename}"
                                    
                                    # 创建本地附件链接
                                    a_tag = soup.new_tag('a')
                                    a_tag.string = f"📎 {link_text}"  # 添加附件图标
                                    a_tag['href'] = local_attachment_path
                                    a_tag['class'] = 'attachment-link'
                                    a_tag['target'] = '_blank'  # 在新标签页中打开
                                    
                                    # 对于可预览的文件（如PDF），不添加download属性，让浏览器直接预览
                                    # 对于其他文件，添加download属性强制下载
                                    previewable_formats = {'.pdf', '.txt', '.json', '.xml', '.csv'}
                                    file_ext = Path(attachment_filename).suffix.lower()
                                    if file_ext not in previewable_formats:
                                        a_tag['download'] = attachment_filename
                                    
                                    # 替换原来的a标签
                                    link.replace_with(a_tag)
                                    logger.debug(f"转换为本地附件链接: {href} -> {local_attachment_path}")
                                else:
                                    # 附件下载失败，显示为失败提示
                                    span = soup.new_tag('span')
                                    span.string = f"❌ {link_text} (下载失败)"
                                    span['class'] = 'failed-attachment'
                                    span['style'] = 'color: #c92a2a; font-weight: bold; border-bottom: 1px dotted #c92a2a;'
                                    
                                    # 替换原来的a标签
                                    link.replace_with(span)
                                    logger.warning(f"附件下载失败，转换为失败提示: {href}")
                            else:
                                # 检查是否是section或category链接
                                if '/hc/kb/section/' in href or '/hc/kb/category/' in href:
                                    # section和category链接转换为纯文字
                                    link_type = 'section' if '/hc/kb/section/' in href else 'category'
                                    logger.debug(f"将{link_type}链接转换为纯文本: {href}")
                                    
                                    span = soup.new_tag('span')
                                    span.string = link_text
                                    span['class'] = f'{link_type}-text'
                                    span['style'] = 'color: #6b7280; font-weight: normal;'
                                    
                                    # 替换原来的a标签
                                    link.replace_with(span)
                                    logger.debug(f"section链接转换为文字: {href}")
                                else:
                                    # 对于其他外部链接，保持为可点击的超链接
                                    # 添加外部链接标识和样式
                                    link['class'] = 'external-link'
                                    link['target'] = '_blank'  # 在新标签页打开
                                    link['rel'] = 'noopener noreferrer'  # 安全属性
                                
                                # 保持原始链接文本，不添加图标
                                
                                logger.debug(f"保持外部链接: {href}")
        
        # 为标题添加id属性以支持锚点导航
        self._add_heading_ids(soup)
        
        return str(soup), downloaded_files
    
    def _add_heading_ids(self, soup):
        """为标题标签添加id属性以支持锚点导航"""
        import re
        
        # 定义标题与步骤ID的映射
        step_mapping = {
            '前言': 'step1',
            '视频学习': 'step8', 
            '功能梳理': 'step2',
            'Demo演示': 'step3',
            '效果图': 'step3',  # 效果图可能是Demo演示的别名
            '如何实现？': 'step4',
            '如何实现': 'step4',
            '代码分享': 'step5',
            '代码共享': 'step5',
            'Demo代码使用条款': 'step6',
            '注意事项': 'step7',
            '最后': 'step9'
        }
        
        # 查找所有h1-h6标题
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text().strip()
            
            # 清理标题文本，移除特殊字符
            clean_text = re.sub(r'[？?！!。.]', '', heading_text)
            
            # 查找匹配的步骤ID
            step_id = None
            for key, value in step_mapping.items():
                if key in clean_text:
                    step_id = value
                    break
            
            # 如果找到匹配的步骤ID，添加id属性
            if step_id and not heading.get('id'):
                heading['id'] = step_id
                logger.debug(f"为标题 '{heading_text}' 添加id: {step_id}")
    
    def get_download_stats(self) -> Dict[str, int]:
        """获取下载统计信息"""
        return {
            'images_downloaded': len(self.downloaded_images),
            'attachments_downloaded': len(self.downloaded_attachments),
            'total_downloaded': len(self.downloaded_images) + len(self.downloaded_attachments),
            'failed': len(self.failed_downloads),
            'total_attempted': len(self.downloaded_images) + len(self.downloaded_attachments) + len(self.failed_downloads)
        }
    
    def cleanup_unused_images(self, used_images: Set[str]) -> int:
        """清理未使用的图片文件"""
        if not self.images_dir.exists():
            return 0
        
        cleaned_count = 0
        
        for image_file in self.images_dir.glob('*'):
            if image_file.is_file() and image_file.name not in used_images:
                try:
                    image_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"清理未使用的图片: {image_file.name}")
                except Exception as e:
                    logger.error(f"清理图片失败 {image_file.name}: {e}")
        
        return cleaned_count


class HTMLGenerator:
    """HTML生成器"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.html_dir = output_dir / "html"
        self.html_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_article_html(self, article, html_content: str, images: List[str] = None) -> Path:
        """生成单个文章的HTML文件"""
        if not article.title:
            return None
        
        # 创建分类目录
        category_parts = article.category.split('/') if hasattr(article, 'category') and article.category else ['其他']
        category_dir = self.html_dir
        
        for part in category_parts:
            category_dir = category_dir / get_safe_filename(part)
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成HTML文件名 (包含文章ID以便链接)
        import re
        article_id = ""
        if hasattr(article, 'url') and article.url:
            id_match = re.search(r'/hc/kb/article/(\d+)', article.url)
            if id_match:
                article_id = id_match.group(1)

        safe_title = get_safe_filename(article.title)
        if article_id:
            html_file = category_dir / f"{article_id}_{safe_title}.html"
        else:
            html_file = category_dir / f"{safe_title}.html"
        
        # 生成HTML内容
        html_template = self._get_html_template()

        # 计算分类层级深度
        category_depth = len(category_parts)
        
        # 计算base路径 - 回到output目录的根目录
        # 需要额外的一层"../"来回到html目录的上一级（output_tiny根目录）
        base_path = "../" * (category_depth + 1)
        
        # 由于HTML使用了base标签指向output根目录，
        # 所有路径都应该直接基于output目录，不需要../前缀
        index_link = "index.html"
        css_path = "css/article.css"
        
        # 准备元数据
        metadata = {
            'title': article.title,
            'category': getattr(article, 'category', ''),
            'section': getattr(article, 'section_title', ''),
            'last_updated': getattr(article, 'last_updated', ''),
            'scraped_at': getattr(article, 'scraped_at', ''),
            'content_length': f"{getattr(article, 'content_length', 0)} 字符",
            'images_count': len(getattr(article, 'image_paths', []))
        }

        # 填充模板
        final_html = html_template.replace('{title}', str(metadata['title']))
        final_html = final_html.replace('{category}', str(metadata['category']))
        final_html = final_html.replace('{section}', str(metadata['section']))
        final_html = final_html.replace('{last_updated}', str(metadata['last_updated']))
        final_html = final_html.replace('{scraped_at}', str(metadata['scraped_at']))
        final_html = final_html.replace('{content_length}', str(metadata['content_length']))
        final_html = final_html.replace('{images_count}', str(metadata['images_count']))
        final_html = final_html.replace('{content}', str(html_content))
        final_html = final_html.replace('{index_link}', index_link)
        final_html = final_html.replace('{css_path}', css_path)
        final_html = final_html.replace('{base_path}', base_path)
        
        # 保存HTML文件
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(final_html)
        
        logger.debug(f"HTML文件已生成: {html_file}")
        return html_file
    
    def _get_html_template(self) -> str:
        """获取HTML模板"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - kintone开发者文档</title>
    <base href="{base_path}">
    <link rel="stylesheet" href="{css_path}">
    <!-- Prism syntax highlighting -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs/themes/prism.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs/plugins/line-numbers/prism-line-numbers.min.css">
</head>
<body>
    <nav class="navbar">
        <div class="navbar-content">
            <a href="{index_link}" class="navbar-brand">📚 kintone开发者文档</a>
            <div class="navbar-links">
                <a href="{index_link}" class="navbar-link back-to-home">← 返回首页</a>
            </div>
        </div>
    </nav>

    <div class="header">
        <h1>{title}</h1>
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-label">📂 分类:</span>
                <span class="metadata-value">{category}</span>
            </div>
            <div class="metadata-item">
                <span class="metadata-label">📊 长度:</span>
                <span class="metadata-value">{content_length}</span>
            </div>
        </div>
    </div>
    
    <div class="content">
        {content}
    </div>
    
    <div class="footer">
        <p>本文档由 kintone-scraper 自动抓取生成</p>
        <p>原始内容版权归 cybozu 所有</p>
    </div>
    
    <a href="#" class="back-to-top" onclick="window.scrollTo(0,0); return false;">↑</a>

    <!-- Prism core + autoloader -->
    <script src="https://cdn.jsdelivr.net/npm/prismjs/prism.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs/plugins/autoloader/prism-autoloader.min.js"></script>
    <script>
      (function(){
        if (window.Prism && Prism.plugins && Prism.plugins.autoloader) {
          Prism.plugins.autoloader.languages_path = 'https://cdn.jsdelivr.net/npm/prismjs/components/';
        }
        function inferLanguage(text){
          const t = (text || '').trim();
          if (!t) return null;
          if (/^\{[\s\S]*\}$/.test(t) || /^\[/.test(t)) { try { JSON.parse(t); return 'json'; } catch(e){} }
          if (/<\/?[a-zA-Z]/.test(t)) return 'markup';
          if (/^(\$ |curl |#\!\/|sudo |apt |yum |brew )/m.test(t)) return 'bash';
          if (/(import |from |def |class |print\(|lambda )/.test(t)) return 'python';
          if (/(const |let |var |=>|function\s+\w+\()/.test(t)) return 'javascript';
          if (/(SELECT |INSERT |UPDATE |DELETE |CREATE TABLE)/i.test(t)) return 'sql';
          return null;
        }
        function mapBrushToPrism(brush){
          const m = String(brush || '').toLowerCase();
          const map = { js:'javascript', javascript:'javascript', ts:'typescript', typescript:'typescript',
                        html:'markup', xml:'markup', markup:'markup', json:'json', css:'css',
                        bash:'bash', shell:'bash', sh:'bash', sql:'sql', java:'java', py:'python', python:'python',
                        yaml:'yaml', yml:'yaml', ini:'ini', txt:'none' };
          return map[m] || null;
        }
        function enhanceCodeBlocks(root){
          const container = root || document;
          const pres = Array.from(container.querySelectorAll('pre'));
          pres.forEach(pre => {
            let lang = null;
            const cls = pre.getAttribute('class') || '';
            const m = cls.match(/brush:([\w-]+)/i);
            if (m) lang = mapBrushToPrism(m[1]);
            let code = pre.querySelector('code');
            if (code) {
              const codeCls = code.getAttribute('class') || '';
              const mm = codeCls.match(/language-([\w-]+)/i);
              if (mm) lang = mm[1];
            }
            if (!lang) {
              const text = (code ? code.textContent : pre.textContent) || '';
              lang = inferLanguage(text) || 'none';
            }
            // ensure we have a <code> child that contains only code text (not action buttons)
            const actions = pre.querySelector('.code-actions');
            if (!code) {
              const rawText = pre.textContent || '';
              // clear pre and reconstruct
              pre.innerHTML = '';
              code = document.createElement('code');
              code.textContent = rawText;
              pre.appendChild(code);
              if (actions) pre.appendChild(actions);
            }
            const langClass = 'language-' + lang;
            if (!code.classList.contains(langClass)) code.classList.add(langClass);
            // add line numbers on pre if multiline
            const textForLines = code.textContent || '';
            if (textForLines.indexOf('\\\\n') !== -1) pre.classList.add('line-numbers');
          });
          if (window.Prism && Prism.highlightAllUnder) {
            Prism.highlightAllUnder(container);
          }
        }
        window.enhanceCodeBlocks = enhanceCodeBlocks;
        document.addEventListener('DOMContentLoaded', function(){
          try { enhanceCodeBlocks(document); } catch(e) {}
        });
      })();
    </script>
    <script>
      // 站内链接（article-link）在单页文章内的处理：跳转到首页并定位到对应文章；若首页无该文章，兜底打开原始链接
      document.addEventListener('click', function(e){
        var el = e.target && e.target.closest ? e.target.closest('a.article-link') : null;
        if (!el) return;
        var aid = el.getAttribute('data-article-id');
        var original = el.getAttribute('data-original-href');
        if (!aid) return;
        e.preventDefault();
        try {
          var indexLink = '{index_link}';
          if (!indexLink) { // 兜底从导航取
            var back = document.querySelector('.navbar .back-to-home');
            indexLink = (back && back.getAttribute('href')) || 'index.html';
          }
          if (indexLink.indexOf('#') !== -1) indexLink = indexLink.split('#')[0];
          var target = indexLink + '#' + String(aid);
          // file:// 下无法探测首页是否包含该ID，这里直接跳首页；
          // 首页若找不到会有提示；如需兜底到原始链接，追加一次跳转
          window.location.href = target;
          // 延迟兜底：若用户返回或首页无内容，可点击历史返回后再次点击触发 original
          if (original) {
            setTimeout(function(){ try { console.debug('fallback to original link if needed'); } catch(e){} }, 0);
          }
        } catch(err) {
          // 最后的兜底：保持原 href 行为或打开原始链接
          if (original) {
            window.location.href = original;
          } else {
            window.location.hash = String(aid);
          }
        }
      }, false);
    </script>
</body>
</html>'''
    
    def _copy_css_files(self):
        """复制CSS文件到输出目录"""
        import shutil
        from pathlib import Path
        
        # 创建css目录
        css_dir = self.output_dir / "css"
        css_dir.mkdir(exist_ok=True)
        
        # 获取CSS源文件路径
        css_source_dir = Path(__file__).parent / "css"
        
        # 复制CSS文件
        if css_source_dir.exists():
            for css_file in css_source_dir.glob("*.css"):
                dest_file = css_dir / css_file.name
                shutil.copy2(css_file, dest_file)
                print(f"已复制CSS文件: {css_file.name} -> {dest_file}")
        else:
            print(f"CSS源目录不存在: {css_source_dir}")

    def generate_index_html(self, categories: List, articles: List) -> Path:
        """生成Vue风格的索引页面"""
        # index.html应该在输出目录的根目录，和html、images目录平级
        index_file = self.output_dir / "index.html"
        
        # 复制CSS文件到输出目录
        self._copy_css_files()
        
        # 若传入的 articles 未包含全部现有文件（例如启用增量跳过时），
        # 从 html 目录补全本地已存在的文章，保证索引完整
        try:
            augmented = self._augment_articles_from_files(articles)
            articles = augmented
        except Exception as e:
            logger.warning(f"补全本地文章列表失败，使用原始列表: {e}")
        
        # 生成分类统计
        category_stats = {}
        for article in articles:
            cat = getattr(article, 'category', '') or '其他'
            category_stats[cat] = category_stats.get(cat, 0) + 1
        
        # 生成导航树和文章内容
        navigation_tree_html = self._generate_navigation_tree(articles)
        article_contents_html = self._generate_article_contents(articles)

        template = self._get_index_template()
        html_content = template.replace('{total_articles}', str(len(articles)))
        html_content = html_content.replace('{total_categories}', str(len(category_stats)))
        html_content = html_content.replace('{navigation_tree}', navigation_tree_html)
        html_content = html_content.replace('{article_contents}', article_contents_html)
        
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 修复所有文章间的链接
        self._fix_article_links(articles)
        
        # 修复index.html中的链接
        self._fix_index_html_links(index_file, articles)
        
        logger.info(f"索引页面已生成: {index_file}")
        return index_file

    def _augment_articles_from_files(self, articles: List) -> List:
        """将磁盘上已有的 html 文章补充到列表中，避免索引缺篇。
        - 从 html/ 递归扫描 {category_path}/{id}_{title}.html
        - 若传入列表中没有该 id，则创建一个轻量“文章对象”补上
        """
        from types import SimpleNamespace
        import re, os
        html_root = self.html_dir
        if not html_root.exists():
            return articles
        
        # 已有文章的ID集合（从url里提取）
        existing_ids = set()
        for a in articles:
            if hasattr(a, 'url') and a.url:
                m = re.search(r'/hc/kb/article/(\d+)', a.url)
                if m:
                    existing_ids.add(m.group(1))
        
        # 扫描磁盘文件
        augmented = list(articles)
        for file in html_root.rglob('*.html'):
            if file.name.lower() == 'index.html':
                continue
            # 相对类别路径
            rel = file.relative_to(html_root)
            parts = list(rel.parts)
            if not parts:
                continue
            filename = parts[-1]
            cat_parts = parts[:-1]
            category = '/'.join(cat_parts) if cat_parts else '其他'
            m = re.match(r'^(\d+)_([^\\/]+)\.html$', filename)
            if not m:
                continue
            aid, title = m.group(1), m.group(2)
            if aid in existing_ids:
                continue
            # 构造最小字段集合（供导航与内容渲染）
            url = f"/hc/kb/article/{aid}/"
            augmented.append(SimpleNamespace(url=url, title=title, category=category))
        return augmented
    
    def _get_index_template(self) -> str:
        """获取索引页面模板 - Vue文档风格"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>kintone开发者文档 - 离线版本</title>
    
    <!-- 现代化图标字体 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <link rel="stylesheet" href="css/index.css">
    <!-- Prism syntax highlighting -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs/themes/prism.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs/plugins/line-numbers/prism-line-numbers.min.css">
</head>
<body>
    <div class="header">
        <h1>kintone开发者文档</h1>
        <div class="stats">
            <span>{total_articles} 篇文章</span>
            <span>{total_categories} 个分类</span>
        </div>
    </div>

    <div class="main-container">
        <div class="sidebar">
            <div class="nav-tree">
                {navigation_tree}
            </div>
        </div>
        
        <div class="content-area">
            <div class="content-welcome" id="welcome-content">
                <h2>📚 kintone开发者文档</h2>
                <p>点击左侧导航选择要查看的文章</p>
            </div>
            
            <div class="loading" id="loading">
                <p>加载中...</p>
            </div>
            
            {article_contents}
        </div>
    </div>

    <!-- Prism core + autoloader -->
    <script src="https://cdn.jsdelivr.net/npm/prismjs/prism.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs/plugins/autoloader/prism-autoloader.min.js"></script>

    <script>
        let currentArticle = '';
        let articlesData = {};
        const HASH_PREFIX = 'article-';

        function makeArticleHash(articleId, sectionId) {
            if (!articleId) {
                return '';
            }
            const encodedId = encodeURIComponent(String(articleId));
            let hash = '#' + HASH_PREFIX + encodedId;
            if (sectionId) {
                hash += ':' + encodeURIComponent(String(sectionId));
            }
            return hash;
        }

        function parseArticleHash(hash) {
            if (!hash) {
                return null;
            }
            const raw = hash.replace(/^#/, '');
            if (!raw.startsWith(HASH_PREFIX)) {
                return null;
            }
            const remainder = raw.slice(HASH_PREFIX.length);
            const splitIndex = remainder.indexOf(':');
            const idPart = splitIndex === -1 ? remainder : remainder.slice(0, splitIndex);
            const sectionPart = splitIndex === -1 ? '' : remainder.slice(splitIndex + 1);
            if (!idPart) {
                return null;
            }
            return {
                articleId: decodeURIComponent(idPart),
                sectionId: sectionPart ? decodeURIComponent(sectionPart) : null
            };
        }

        function escapeForSelector(value) {
            if (window.CSS && window.CSS.escape) {
                return window.CSS.escape(value);
            }
            return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');
        }

        function focusSection(articleId, sectionId, smooth) {
            if (!articleId || !sectionId) {
                return;
            }
            const articleContent = document.getElementById('article-' + articleId);
            if (!articleContent) {
                return;
            }
            const safeSection = escapeForSelector(sectionId);
            let target = articleContent.querySelector('#' + safeSection);
            if (!target) {
                target = articleContent.querySelector('[id="' + safeSection + '"]');
            }
            if (!target) {
                target = articleContent.querySelector('[name="' + safeSection + '"]');
            }
            if (target && target.scrollIntoView) {
                target.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
            }
        }

        function updateLocationHash(articleId, sectionId) {
            const targetHash = makeArticleHash(articleId, sectionId);
            if (!targetHash) {
                return;
            }
            if (window.location.hash !== targetHash) {
                window.location.hash = targetHash;
            }
        }


        // 代码高亮增强（Prism + brush映射 + 启发式）
        (function(){
            if (window.Prism && Prism.plugins && Prism.plugins.autoloader) {
                Prism.plugins.autoloader.languages_path = 'https://cdn.jsdelivr.net/npm/prismjs/components/';
            }
            function inferLanguage(text){
              const t = (text || '').trim();
              if (!t) return null;
              if (/^\{[\s\S]*\}$/.test(t) || /^\[/.test(t)) { try { JSON.parse(t); return 'json'; } catch(e){} }
              if (/<\/?[a-zA-Z]/.test(t)) return 'markup';
              if (/^(\$ |curl |#\!\/|sudo |apt |yum |brew )/m.test(t)) return 'bash';
              if (/(import |from |def |class |print\(|lambda )/.test(t)) return 'python';
              if (/(const |let |var |=>|function\s+\w+\()/.test(t)) return 'javascript';
              if (/(SELECT |INSERT |UPDATE |DELETE |CREATE TABLE)/i.test(t)) return 'sql';
              return null;
            }
            function mapBrushToPrism(brush){
              const m = String(brush || '').toLowerCase();
              const map = { js:'javascript', javascript:'javascript', ts:'typescript', typescript:'typescript',
                            html:'markup', xml:'markup', markup:'markup', json:'json', css:'css',
                            bash:'bash', shell:'bash', sh:'bash', sql:'sql', java:'java', py:'python', python:'python',
                            yaml:'yaml', yml:'yaml', ini:'ini', txt:'none' };
              return map[m] || null;
            }
            window.enhanceCodeBlocks = function(root){
              const container = root || document;
              const pres = Array.from(container.querySelectorAll('pre'));
              pres.forEach(pre => {
                let lang = null;
                const cls = pre.getAttribute('class') || '';
                const m = cls.match(/brush:([\w-]+)/i);
                if (m) lang = mapBrushToPrism(m[1]);
                let code = pre.querySelector('code');
                if (code) {
                  const codeCls = code.getAttribute('class') || '';
                  const mm = codeCls.match(/language-([\w-]+)/i);
                  if (mm) lang = mm[1];
                }
                if (!lang) {
                  const text = (code ? code.textContent : pre.textContent) || '';
                  lang = inferLanguage(text) || 'none';
                }
                const actions = pre.querySelector('.code-actions');
                if (!code) {
                  const rawText = pre.textContent || '';
                  pre.innerHTML = '';
                  code = document.createElement('code');
                  code.textContent = rawText;
                  pre.appendChild(code);
                  if (actions) pre.appendChild(actions);
                }
                const langClass = 'language-' + lang;
                if (!code.classList.contains(langClass)) code.classList.add(langClass);
                const textForLines = code.textContent || '';
                if (textForLines.indexOf('\\\\n') !== -1) pre.classList.add('line-numbers');
              });
              if (window.Prism && Prism.highlightAllUnder) {
                Prism.highlightAllUnder(container);
              }
            };
        })();

        // 现代化树形导航控制
        function toggleTreeNode(nodeId) {
            const node = document.getElementById(nodeId);
            if (!node) {
                console.error('Node not found:', nodeId);
                return;
            }
            
            const header = node.querySelector('.tree-node-header');
            const children = node.querySelector('.tree-node-children');
            const expandIcon = header ? header.querySelector('.tree-icon.expandable') : null;
            
            if (node.classList.contains('expanded')) {
                // 收起
                node.classList.remove('expanded');
                if (children) {
                    // 移除内联样式，让CSS类控制
                    children.style.removeProperty('max-height');
                    children.style.removeProperty('opacity');
                }
                if (expandIcon) expandIcon.style.transform = 'rotate(0deg)';
            } else {
                // 展开
                node.classList.add('expanded');
                if (children) {
                    // 移除内联样式，让CSS类控制
                    children.style.removeProperty('max-height');
                    children.style.removeProperty('opacity');
                }
                if (expandIcon) expandIcon.style.transform = 'rotate(90deg)';
            }
        }
        

        // 显示文章内容
        function showArticle(articleId, options = {}) {
            const { sectionId = null, updateHash = true, scrollIntoView = true } = options || {};

            // 隐藏欢迎页面
            document.getElementById('welcome-content').style.display = 'none';

            // 隐藏所有文章内容
            document.querySelectorAll('.article-content').forEach(function(content) {
                content.classList.remove('active');
            });

            // 显示选中的文章
            const articleContent = document.getElementById('article-' + articleId);
            if (articleContent) {
                articleContent.classList.add('active');
                currentArticle = articleId;

                // 为当前文章的代码块添加复制按钮
                initCodeCopyButtons(articleContent);
                try { enhanceCodeBlocks(articleContent); } catch (e) {}

                setupInternalAnchors(articleContent, articleId);

                if (!updateHash && sectionId && scrollIntoView) {
                    focusSection(articleId, sectionId, scrollIntoView);
                }

                if (updateHash) {
                    updateLocationHash(articleId, sectionId);
                }
            } else {
                // 如果文章不存在，显示友好提示
                const missingMessage = '文章 ID ' + articleId + ' 未包含在当前离线文档中。' + '\\n\\n' + '这可能是因为该文章在其他分类中，或者需要完整抓取才能获取。';
                alert(missingMessage);
            }
        }

        function setupInternalAnchors(articleContent, articleId) {
            if (!articleContent) {
                return;
            }
            const anchors = articleContent.querySelectorAll('a[href^="#"]');
            anchors.forEach(function(anchor) {
                if (anchor.dataset && anchor.dataset.hashBound === '1') {
                    return;
                }
                if (anchor.dataset) {
                    anchor.dataset.hashBound = '1';
                } else {
                    anchor.setAttribute('data-hash-bound', '1');
                }
                anchor.addEventListener('click', function(event) {
                    const href = anchor.getAttribute('href');
                    if (!href || href === '#') {
                        return;
                    }
                    const rawSection = href.slice(1);
                    if (!rawSection) {
                        return;
                    }
                    event.preventDefault();
                    let decodedSection = rawSection;
                    try { decodedSection = decodeURIComponent(rawSection); } catch (err) {}
                    const targetHash = makeArticleHash(articleId, decodedSection);
                    if (window.location.hash === targetHash) {
                        focusSection(articleId, decodedSection, true);
                    } else {
                        window.location.hash = targetHash;
                    }
                });
            });
        }

        // 初始化代码复制按钮
        function initCodeCopyButtons(container) {
            const preBlocks = container.querySelectorAll('pre');
            preBlocks.forEach(function(pre) {
                // 检查是否已经有按钮容器
                if (pre.querySelector('.code-actions')) {
                    return;
                }
                
                // 添加标记类
                pre.classList.add('has-actions');
                
                // 创建按钮容器
                const actionsContainer = document.createElement('div');
                actionsContainer.className = 'code-actions';
                
                // 创建换行切换按钮
                const wrapBtn = document.createElement('button');
                wrapBtn.className = 'wrap-btn';
                wrapBtn.textContent = '换行';
                wrapBtn.title = '切换代码换行';
                wrapBtn.onclick = function() {
                    pre.classList.toggle('wrapped');
                    if (pre.classList.contains('wrapped')) {
                        wrapBtn.textContent = '不换行';
                        wrapBtn.classList.add('active');
                    } else {
                        wrapBtn.textContent = '换行';
                        wrapBtn.classList.remove('active');
                    }
                };
                
                // 创建复制按钮
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-btn';
                copyBtn.textContent = '复制';
                copyBtn.title = '复制代码';
                copyBtn.onclick = function() {
                    const codeText = pre.textContent || pre.innerText;
                    // 移除按钮文本
                    const textToCopy = codeText.replace(/^(换行|不换行)?\s*复制\s*/, '');
                    
                    copyToClipboard(textToCopy, function(success) {
                        if (success) {
                            copyBtn.textContent = '已复制!';
                            copyBtn.classList.add('copied');
                            setTimeout(function() {
                                copyBtn.textContent = '复制';
                                copyBtn.classList.remove('copied');
                            }, 2000);
                        } else {
                            copyBtn.textContent = '失败';
                            setTimeout(function() {
                                copyBtn.textContent = '复制';
                            }, 2000);
                        }
                    });
                };
                
                // 添加按钮到容器
                actionsContainer.appendChild(wrapBtn);
                actionsContainer.appendChild(copyBtn);
                pre.appendChild(actionsContainer);
            });
        }
        
        // 复制到剪贴板的辅助函数
        function copyToClipboard(text, callback) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(
                    function() { callback(true); },
                    function() { callback(false); }
                );
            } else {
                // 旧版浏览器的兼容方案
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                try {
                    const successful = document.execCommand('copy');
                    callback(successful);
                } catch (err) {
                    callback(false);
                }
                
                document.body.removeChild(textArea);
            }
        }

        function handleHashNavigation(scrollToTarget) {
            if (scrollToTarget === undefined) {
                scrollToTarget = true;
            }
            const info = parseArticleHash(window.location.hash);
            if (info) {
                showArticle(info.articleId, { updateHash: false, sectionId: info.sectionId, scrollIntoView: scrollToTarget });
                if (!info.sectionId && scrollToTarget) {
                    if (typeof window.scrollTo === 'function') {
                        window.scrollTo({ top: 0, behavior: 'auto' });
                    }
                }
            } else if (!window.location.hash) {
                showWelcome();
            }
        }

        // 显示欢迎页面
        function showWelcome() {
            document.getElementById('welcome-content').style.display = 'flex';
            
            // 隐藏所有文章内容
            document.querySelectorAll('.article-content').forEach(content => {
                content.classList.remove('active');
            });
            
            currentArticle = '';
        }

        // 初始化页面
        document.addEventListener('DOMContentLoaded', function() {
            // 确保所有节点默认是折叠状态（通过移除expanded类）
            document.querySelectorAll('.tree-node').forEach(function(node) {
                node.classList.remove('expanded');
            });
            handleHashNavigation(false);
        });

        window.addEventListener('hashchange', function() {
            handleHashNavigation(true);
        });
    </script>
</body>
</html>"""

    def _generate_navigation_tree(self, articles: List) -> str:
        """生成Vue风格的导航树HTML"""
        # 按分类组织文章
        categories = {}
        for article in articles:
            category = getattr(article, 'category', '') or '其他'
            if category not in categories:
                categories[category] = []
            categories[category].append(article)
        
        # 组织成层级结构
        hierarchy = {}
        for category, articles_list in categories.items():
            parts = (category or '其他').split('/')
            if len(parts) >= 2:
                parent = parts[0]
                child = parts[1]
                if parent not in hierarchy:
                    hierarchy[parent] = {}
                hierarchy[parent][child] = articles_list
            else:
                # 单级分类
                if category not in hierarchy:
                    hierarchy[category] = {}
                hierarchy[category]['_articles'] = articles_list
        
        # 定义分类显示顺序
        category_order = [
            "新手教程", "API文档", "工具", "插件", "开发范例", "应用场景",
            "其他", "开发学习视频专栏", "通知", "账号&协议"
        ]
        
        # 按照指定顺序排序分类
        def sort_categories(item):
            category = item[0]
            try:
                return category_order.index(category)
            except ValueError:
                # 如果分类不在指定列表中，放到最后
                return len(category_order)
        
        sorted_hierarchy = sorted(hierarchy.items(), key=sort_categories)
        
        # 生成现代化HTML结构
        html_parts = []
        for parent_category, children in sorted_hierarchy:
            # 主分类节点
            safe_parent = parent_category.replace('/', '-').replace(' ', '-')
            html_parts.append(f'''
            <div class="tree-node level-1" id="node-{safe_parent}">
                <div class="tree-node-header" onclick="toggleTreeNode('node-{safe_parent}')">
                    <i class="tree-icon expandable fas fa-chevron-right"></i>
                    <i class="tree-icon fas fa-folder"></i>
                    <span class="tree-text">{parent_category}</span>
                </div>
                <div class="tree-node-children">''')
            
            # 子分类或直接文章
            for child_name, articles_list in children.items():
                if child_name == '_articles':
                    # 直接显示文章（没有子分类）
                    for article in articles_list:
                        article_id = self._extract_article_id(article)
                        html_parts.append(f'''
                    <div class="tree-node level-3">
                        <div class="tree-node-header" onclick="showArticle('{article_id}')">
                            <i class="tree-icon fas fa-file-alt"></i>
                            <span class="tree-text">{article.title}</span>
                        </div>
                    </div>''')
                else:
                    # 子分类节点
                    safe_child = f"{safe_parent}-{child_name.replace('/', '-').replace(' ', '-')}"
                    html_parts.append(f'''
                    <div class="tree-node level-2" id="node-{safe_child}">
                        <div class="tree-node-header" onclick="toggleTreeNode('node-{safe_child}')">
                            <i class="tree-icon expandable fas fa-chevron-right"></i>
                            <i class="tree-icon fas fa-folder-open"></i>
                            <span class="tree-text">{child_name}</span>
                            <span class="article-count">{len(articles_list)}</span>
                        </div>
                        <div class="tree-node-children">''')
                    
                    # 子分类下的文章
                    for article in articles_list:
                        article_id = self._extract_article_id(article)
                        html_parts.append(f'''
                            <div class="tree-node level-3">
                                <div class="tree-node-header" onclick="showArticle('{article_id}')">
                                    <i class="tree-icon fas fa-file-alt"></i>
                                    <span class="tree-text">{article.title}</span>
                                </div>
                            </div>''')
                    
                    html_parts.append('                        </div>\n                    </div>')
            
            html_parts.append('                </div>\n            </div>')
        
        return '\n'.join(html_parts)
    
    def _fix_image_paths_for_index(self, html_content: str) -> str:
        """修复HTML内容中的图片路径，适应主页面index.html的位置"""
        import re
        
        # 将 ../../../images/ 替换为 images/
        # 这是因为文章页面在 html/分类/子分类/ 中，而主页面在根目录中
        html_content = re.sub(r'src="(\.\./)+images/', 'src="images/', html_content)
        
        return html_content
    
    def _extract_article_id(self, article) -> str:
        """从文章URL中提取ID"""
        import re
        if hasattr(article, 'url') and article.url:
            id_match = re.search(r'/hc/kb/article/(\d+)', article.url)
            if id_match:
                return id_match.group(1)
        # 如果没有ID，使用安全的标题作为ID
        return get_safe_filename(article.title)[:20]
    
    def _generate_article_contents(self, articles: List) -> str:
        """生成所有文章的内容HTML"""
        contents = []
        
        for article in articles:
            if not hasattr(article, 'title') or not article.title:
                continue
                
            article_id = self._extract_article_id(article)
            
            # 读取文章的HTML内容
            category_parts = (getattr(article, 'category', '') or '其他').split('/')
            category_dir = self.html_dir
            for part in category_parts:
                category_dir = category_dir / get_safe_filename(part)
            
            safe_title = get_safe_filename(article.title)
            import re
            url_id = ""
            if hasattr(article, 'url') and article.url:
                id_match = re.search(r'/hc/kb/article/(\d+)', article.url)
                if id_match:
                    url_id = id_match.group(1)
            
            if url_id:
                html_file = category_dir / f"{url_id}_{safe_title}.html"
            else:
                html_file = category_dir / f"{safe_title}.html"
            
            article_content = ""
            if html_file.exists():
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 提取body内容
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # 尝试多种可能的内容容器，但提取其内部HTML而非整个容器
                        body_content = (soup.find('div', class_='article-body') or 
                                      soup.find('div', class_='content-body') or 
                                      soup.find('div', class_='main-content') or
                                      soup.find('main') or
                                      soup.find('article'))
                        
                        if body_content:
                            # 清理和提取内容，避免重复标题和嵌套结构
                            content_copy = BeautifulSoup(str(body_content), 'html.parser')
                            
                            # 移除重复的标题（保留主要内容）
                            for header in content_copy.find_all(['header', '.article-header']):
                                if header:
                                    header.decompose()
                            
                            # 移除重复的article-content嵌套
                            nested_content = content_copy.find('div', class_='article-content')
                            if nested_content:
                                # 提取嵌套内容的子元素到父级
                                nested_children = nested_content.find_all(recursive=False)
                                for child in nested_children:
                                    nested_content.parent.append(child)
                                nested_content.decompose()
                            
                            # 查找主要内容区域
                            main_content = (content_copy.find('div', class_='original-content') or 
                                          content_copy.find('div', class_='content') or
                                          content_copy)
                            
                            if main_content:
                                inner_html = main_content.decode_contents() if hasattr(main_content, 'decode_contents') else str(main_content)
                            else:
                                inner_html = content_copy.decode_contents() if hasattr(content_copy, 'decode_contents') else str(content_copy)
                            
                            # 修复图片路径：从文章页面的相对路径调整为主页面的相对路径
                            inner_html = self._fix_image_paths_for_index(inner_html)
                            article_content = f"<div class='article-body'>{inner_html}</div>"
                        else:
                            # 如果找不到特定容器，提取body中的主要内容
                            body = soup.find('body')
                            if body:
                                # 移除导航、头部、脚部、脚本等不需要的元素
                                for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style', '.navbar', '.back-to-home']):
                                    if tag:
                                        tag.decompose()
                                
                                # 查找主要内容区域
                                main_content = body.find(['main', 'article', '.content', '.main'])
                                if main_content:
                                    article_content = f"<div class='article-body'>{main_content.decode_contents()}</div>"
                                else:
                                    # 最后的备选方案，提取所有文本内容
                                    text_content = body.get_text(separator='\n', strip=True)
                                    if len(text_content) > 100:
                                        article_content = f"<div class='article-body'><pre>{text_content[:2000]}...</pre></div>"
                                    else:
                                        article_content = "<div class='article-body'>内容为空或无法提取</div>"
                            else:
                                article_content = "<div class='article-body'>无法找到body标签</div>"
                except Exception as e:
                    article_content = f"<div class='article-body'>内容加载出错: {e}</div>"
            else:
                article_content = f"<div class='article-body'>文章文件未找到: {html_file}</div>"
            
            # 生成文章内容HTML
            contents.append(f'''
            <div class="article-content" id="article-{article_id}">
                <div class="article-header">
                    <h1 class="article-title">{article.title}</h1>
                    <div class="article-meta">
                        <span>分类: {getattr(article, 'category', '未知')}</span>
                    </div>
                </div>
                {article_content}
            </div>''')
        
        return ''.join(contents)

    def _fix_article_links(self, articles: List) -> None:
        """修复所有文章间的链接"""
        logger.info("开始修复文章间的链接...")
        
        # 1. 建立文章ID到文件路径的映射
        article_map = {}
        for article in articles:
            # 提取文章ID
            import re
            if hasattr(article, 'url') and article.url:
                id_match = re.search(r'/hc/kb/article/(\d+)', article.url)
                if id_match:
                    article_id = id_match.group(1)
                    
                    # 生成文件路径
                    category_parts = getattr(article, 'category', '其他').split('/')
                    safe_parts = [get_safe_filename(part) for part in category_parts]
                    relative_path = '/'.join(safe_parts)
                    
                    # 文件名：ID_标题.html
                    safe_title = get_safe_filename(article.title)
                    filename = f"{article_id}_{safe_title}.html"
                    
                    article_map[article_id] = f"{relative_path}/{filename}"
        
        logger.info(f"建立了 {len(article_map)} 个文章的路径映射")
        
        # 2. 遍历所有HTML文件，替换article://链接
        html_files = list(self.html_dir.rglob("*.html"))
        fixed_count = 0
        
        for html_file in html_files:
            if html_file.name == "index.html":
                continue
                
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # 替换所有article://链接
                import re
                def replace_article_link(match):
                    article_id = match.group(1)
                    if article_id in article_map:
                        # 计算相对路径
                        current_dir = html_file.parent
                        target_path = self.html_dir / article_map[article_id]
                        
                        # 计算相对路径
                        try:
                            relative_path = os.path.relpath(target_path, current_dir)
                            relative_path = relative_path.replace('\\', '/')  # Windows路径转换
                            return f'href="{relative_path}"'
                        except ValueError:
                            # 如果无法计算相对路径，使用绝对路径
                            return f'href="{article_map[article_id]}"'
                    else:
                        # 如果找不到对应文章，生成预期的本地文件路径
                        # 使用简洁格式：{article_id}.html，放在"其他"分类下
                        expected_path = f"其他/{article_id}.html"
                        try:
                            current_dir = html_file.parent
                            target_path = self.html_dir / expected_path
                            relative_path = os.path.relpath(target_path, current_dir)
                            relative_path = relative_path.replace('\\', '/')  # Windows路径转换
                            return f'href="{relative_path}"'
                        except ValueError:
                            # 如果无法计算相对路径，使用绝对路径
                            return f'href="{expected_path}"'
                
                # 处理各种占位符格式的链接（如果还有的话）
                content = re.sub(r'href="article://(\d+)"', replace_article_link, content)
                content = re.sub(r'href="LOCAL_FILE:(\d+)"', replace_article_link, content)
                content = re.sub(r'href="ARTICLE_ID:(\d+)"', replace_article_link, content)
                
                # 如果内容有变化，保存文件
                if content != original_content:
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    fixed_count += 1
                    
            except Exception as e:
                logger.error(f"处理文件 {html_file} 时出错: {e}")
        
        logger.info(f"修复完成，共处理了 {fixed_count} 个文件")

    def _fix_index_html_links(self, index_file: Path, articles: List) -> None:
        """修复index.html中的文章链接"""
        logger.info("开始修复index.html中的链接...")
        
        # 1. 建立文章ID到文件路径的映射
        import re
        article_map = {}
        for article in articles:
            if hasattr(article, 'url') and article.url:
                id_match = re.search(r'/hc/kb/article/(\d+)', article.url)
                if id_match:
                    article_id = id_match.group(1)
                    
                    # 生成相对于index.html的文件路径
                    category_parts = (getattr(article, 'category', '') or '其他').split('/')
                    safe_parts = [get_safe_filename(part) for part in category_parts]
                    relative_path = '/'.join(safe_parts)
                    
                    # 文件名：ID_标题.html
                    safe_title = get_safe_filename(article.title)
                    filename = f"{article_id}_{safe_title}.html"
                    
                    # index.html在根目录，所以路径需要加上html/前缀
                    article_map[article_id] = f"html/{relative_path}/{filename}"
        
        logger.info(f"建立了 {len(article_map)} 个文章的路径映射（针对index.html）")
        
        # 2. 读取并修复index.html
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 替换链接的函数
            def replace_link(match):
                article_id = match.group(1)
                if article_id in article_map:
                    return f'href="{article_map[article_id]}"'
                else:
                    # 如果找不到对应文章，生成预期的本地文件路径
                    # 使用简洁格式：html/其他/{article_id}.html（相对于index.html）
                    expected_path = f"html/其他/{article_id}.html"
                    return f'href="{expected_path}"'
            
            # 处理各种占位符格式的链接（如果还有的话）
            content = re.sub(r'href="article://(\d+)"', replace_link, content)
            content = re.sub(r'href="LOCAL_FILE:(\d+)"', replace_link, content)
            content = re.sub(r'href="ARTICLE_ID:(\d+)"', replace_link, content)
            
            # 如果内容有变化，保存文件
            if content != original_content:
                with open(index_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info("index.html链接修复完成")
            else:
                logger.info("index.html无需修复")
                
        except Exception as e:
            logger.error(f"修复index.html链接时出错: {e}")

    def _generate_article_list(self, articles: List) -> str:
        """生成文章列表HTML"""
        items = []
        for article in articles:
            if not hasattr(article, 'title') or not article.title:
                continue

            # 生成相对路径（包含文章ID前缀）
            category_parts = getattr(article, 'category', '其他').split('/')
            relative_path = '/'.join(get_safe_filename(part) for part in category_parts)
            
            # 提取文章ID
            import re
            article_id = ""
            if hasattr(article, 'url') and article.url:
                id_match = re.search(r'/hc/kb/article/(\d+)', article.url)
                if id_match:
                    article_id = id_match.group(1)
            
            safe_title = get_safe_filename(article.title)
            if article_id:
                article_path = f"{relative_path}/{article_id}_{safe_title}.html"
            else:
                article_path = f"{relative_path}/{safe_title}.html"

            items.append(f"""
                <li class="article-item" data-category="{getattr(article, 'category', '未知')}">
                    <a href="{article_path}" class="article-title">{article.title}</a>
                </li>
            """)
        return ''.join(items)

        return ''.join(items)
