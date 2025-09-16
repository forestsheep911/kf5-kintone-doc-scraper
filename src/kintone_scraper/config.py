"""配置文件"""

import os
from pathlib import Path
from typing import Dict, List

# 基础配置
BASE_URL = "https://cybozudev.kf5.com/hc/"
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.5  # 请求间隔（秒）
MAX_RETRIES = 3
BATCH_SIZE = 10  # 每批处理的文章数量

# 用户代理
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# 请求头
DEFAULT_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# 选择器配置
SELECTORS = {
    'section_links': 'a.more[href*="/hc/kb/section/"]',
    'category_links': 'a[href*="/hc/kb/category/"]',
    'article_links': 'a[href*="/hc/kb/article/"]',
    'title': ['h1.article-title', '.kb-article-title h1', 'h1', '.article-header h1'],
    'content': ['article'],  # 只提取article标签内的内容
    # 部分页面使用 .breadcrumbs（复数）
    'breadcrumb': '.breadcrumb',
    'breadcrumbs': '.breadcrumbs',
    'last_updated': 'time, .updated-time, .last-modified',
}

# 分类映射 - 将英文URL映射到中文分类名
CATEGORY_MAPPING = {
    'kintone REST API': 'kintone REST API',
    'kintone JavaScript API': 'kintone JavaScript API', 
    'kintone API指南': 'kintone API指南',
    'cybozu User API/OAuth': 'cybozu User API/OAuth',
    'SDK': 'SDK',
    '开发工具': '开发工具',
    '资源库': '资源库',
    '新手入门': '新手入门',
    'kintone API入门系列': 'kintone API入门系列',
    'kintone自定义技巧': 'kintone自定义技巧',
    '插件API/CSS': '插件API/CSS',
    '插件开发': '插件开发',
    '插件范例': '插件范例',
    'API更新信息': 'API更新信息',
    '云上办公解决方案': '云上办公解决方案',
    '才望云开发': '才望云开发',
    '前端技术': '前端技术',
    '前端中级进阶': '前端中级进阶',
    '培训': '培训',
    '共通': '共通',
    '协议规章': '协议规章',
    'kintone开发者账号': 'kintone开发者账号',
    'kintone开发者演示环境': 'kintone开发者演示环境',
}

# 主要分类结构
MAIN_CATEGORIES = {
    'API文档': [
        'kintone REST API',
        'kintone JavaScript API', 
        'kintone API指南',
        'cybozu User API/OAuth'
    ],
    '工具': [
        'SDK',
        '开发工具',
        '资源库'
    ],
    '新手教程': [
        '新手入门',
        'kintone API入门系列',
        'kintone自定义技巧'
    ],
    '插件': [
        '插件API/CSS',
        '插件开发',
        '插件范例'
    ],
    # 站点还有“开发范例”主分类
    '开发范例': [
        '自定义开发'
    ],
    '通知': [
        'API更新信息'
    ],
    '开发学习视频专栏': [
        '云上办公解决方案',
        '才望云开发',
        '前端技术',
        '前端中级进阶',
        '培训'
    ],
    '应用场景': [
        '共通'
    ],
    '账号&协议': [
        '协议规章',
        'kintone开发者账号',
        'kintone开发者演示环境'
    ]
}

# 输出配置
DEFAULT_OUTPUT_DIR = Path("data")
OUTPUT_FORMATS = ['markdown', 'json', 'html']

# B站视频处理配置
BILIBILI_VIDEO_MODE = "iframe"  # 默认使用嵌入播放器模式
# iframe: 直接嵌入视频播放器到页面中，提供更好的用户体验
# link: 生成链接跳转到B站视频页面

# 文件名安全字符替换
FILENAME_SAFE_CHARS = {
    '/': '_',
    '\\': '_',
    ':': '：',
    '*': '＊',
    '?': '？',
    '"': '"',
    '<': '＜',
    '>': '＞',
    '|': '｜',
}

def get_safe_filename(filename: str, max_length: int = 100) -> str:
    """获取安全的文件名"""
    for char, replacement in FILENAME_SAFE_CHARS.items():
        filename = filename.replace(char, replacement)
    
    # 移除开头和结尾的空格和点
    filename = filename.strip(' .')
    
    # 限制长度（在清理后）
    if len(filename) > max_length:
        filename = filename[:max_length-3] + "..."
    
    return filename

def get_category_path(section_title: str) -> str:
    """根据section标题获取分类路径"""
    if not section_title:
        return "其他/未知"

    # 首先尝试直接匹配
    if section_title in CATEGORY_MAPPING:
        mapped_title = CATEGORY_MAPPING[section_title]

        # 查找主分类
        for main_cat, sub_cats in MAIN_CATEGORIES.items():
            if mapped_title in sub_cats:
                return f"{main_cat}/{mapped_title}"

    # 如果没有找到，尝试模糊匹配
    for main_cat, sub_cats in MAIN_CATEGORIES.items():
        for sub_cat in sub_cats:
            if section_title and sub_cat:
                # 检查是否包含关键词
                if (sub_cat in section_title or
                    section_title in sub_cat or
                    any(keyword in section_title.lower() for keyword in sub_cat.lower().split()) or
                    any(keyword in sub_cat.lower() for keyword in section_title.lower().split())):
                    return f"{main_cat}/{sub_cat}"

    # 如果都没找到，放在"其他"分类下
    return f"其他/{section_title}"


def get_article_file_path(article_id: str, section_category_path: str = "", article_title: str = "") -> str:
    """
    根据文章ID、section分类路径和标题生成统一的文件路径

    Args:
        article_id: 文章ID（如 "1427187"）
        section_category_path: section的分类路径（如 "新手教程/kintone自定义技巧"）
        article_title: 文章标题（可选，用于生成更友好的文件名）

    Returns:
        相对于html目录的统一文件路径
    """
    if not article_id:
        return "其他/unknown.html"

    # 如果没有分类信息，使用默认分类
    if not section_category_path or section_category_path == "其他/未知":
        category_path = "其他"
    else:
        # 确保分类路径是安全的文件名格式
        category_path = get_safe_filename(section_category_path.replace('/', '_'))

    # 如果有文章标题，使用ID_标题格式；否则只使用ID
    if article_title:
        safe_title = get_safe_filename(article_title)
        filename = f"{article_id}_{safe_title}.html"
    else:
        filename = f"{article_id}.html"

    # 统一的文件路径格式：分类目录/文件名
    # 例如：新手教程_kintone自定义技巧/1427187_使用TypeScript开发kintone自定义.html
    return f"{category_path}/{filename}"


def calculate_relative_path(from_file_path: str, to_file_path: str) -> str:
    """
    计算从一个HTML文件到另一个HTML文件的相对路径

    Args:
        from_file_path: 起始文件路径（相对于html目录）
        to_file_path: 目标文件路径（相对于html目录）

    Returns:
        相对路径字符串
    """
    import os

    # 将路径转换为系统路径格式
    from_parts = from_file_path.replace('/', os.sep).split(os.sep)
    to_parts = to_file_path.replace('/', os.sep).split(os.sep)

    # 找到共同的前缀
    common_length = 0
    for i, (from_part, to_part) in enumerate(zip(from_parts, to_parts)):
        if from_part == to_part:
            common_length = i + 1
        else:
            break

    # 计算向上级目录的层数（减去文件名部分）
    up_levels = len(from_parts) - common_length - 1
    up_path = "../" * up_levels if up_levels > 0 else ""

    # 构建相对路径
    remaining_parts = to_parts[common_length:]
    if remaining_parts:
        relative_path = up_path + "/".join(remaining_parts)
    else:
        # 如果在同一目录，只需要文件名
        relative_path = to_parts[-1]

    return relative_path if relative_path else "./"
