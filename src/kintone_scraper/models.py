"""数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class Article:
    """文章数据模型"""
    url: str
    title: str = ""
    content: str = ""
    html_content: str = ""
    category: str = ""
    section_title: str = ""
    last_updated: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    content_length: int = field(init=False)
    
    def __post_init__(self):
        """计算内容长度"""
        self.content_length = len(self.content)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'html_content': self.html_content,
            'category': self.category,
            'section_title': self.section_title,
            'last_updated': self.last_updated,
            'scraped_at': self.scraped_at,
            'content_length': self.content_length,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Article':
        """从字典创建实例"""
        return cls(
            url=data['url'],
            title=data.get('title', ''),
            content=data.get('content', ''),
            html_content=data.get('html_content', ''),
            category=data.get('category', ''),
            section_title=data.get('section_title', ''),
            last_updated=data.get('last_updated', ''),
            scraped_at=data.get('scraped_at', datetime.now().isoformat()),
        )


@dataclass
class Section:
    """章节数据模型"""
    url: str
    title: str = ""
    description: str = ""
    article_count: int = field(init=False, default=0)
    articles: List[str] = field(default_factory=list)
    category_path: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        """计算文章数量"""
        if not self.article_count:  # 只有当article_count为0时才自动计算
            self.article_count = len(self.articles)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'url': self.url,
            'title': self.title,
            'description': self.description,
            'article_count': self.article_count,
            'articles': self.articles,
            'category_path': self.category_path,
            'scraped_at': self.scraped_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Section':
        """从字典创建实例"""
        section = cls(
            url=data['url'],
            title=data.get('title', ''),
            description=data.get('description', ''),
            articles=data.get('articles', []),
            category_path=data.get('category_path', ''),
            scraped_at=data.get('scraped_at', datetime.now().isoformat()),
        )
        # 如果字典中有特定的article_count，使用它，否则使用自动计算的值
        if 'article_count' in data:
            section.article_count = data['article_count']
        return section


@dataclass
class Category:
    """分类数据模型"""
    name: str
    path: str
    sections: List[Section] = field(default_factory=list)
    total_articles: int = field(init=False, default=0)
    
    def __post_init__(self):
        """计算总文章数"""
        self.total_articles = sum(section.article_count for section in self.sections)
    
    def add_section(self, section: Section):
        """添加章节"""
        self.sections.append(section)
        self.total_articles += section.article_count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'path': self.path,
            'sections': [section.to_dict() for section in self.sections],
            'total_articles': self.total_articles,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """从字典创建实例"""
        category = cls(
            name=data['name'],
            path=data['path'],
        )
        
        for section_data in data.get('sections', []):
            section = Section.from_dict(section_data)
            category.sections.append(section)
        
        # 重新计算总文章数
        category.total_articles = sum(section.article_count for section in category.sections)
        
        return category


@dataclass
class ScrapingResult:
    """抓取结果数据模型"""
    total_sections: int = 0
    total_articles: int = 0
    successful_articles: int = 0
    failed_articles: int = 0
    categories: List[Category] = field(default_factory=list)
    articles: List[Article] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str = ""
    duration: str = ""
    
    def mark_completed(self):
        """标记抓取完成"""
        self.end_time = datetime.now().isoformat()
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        self.duration = str(end - start)
    
    def add_article(self, article: Article, success: bool = True):
        """添加文章"""
        self.articles.append(article)
        if success:
            self.successful_articles += 1
        else:
            self.failed_articles += 1
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.total_articles == 0:
            return 0.0
        return self.successful_articles / self.total_articles
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'metadata': {
                'total_sections': self.total_sections,
                'total_articles': self.total_articles,
                'successful_articles': self.successful_articles,
                'failed_articles': self.failed_articles,
                'success_rate': self.get_success_rate(),
                'start_time': self.start_time,
                'end_time': self.end_time,
                'duration': self.duration,
            },
            'categories': [category.to_dict() for category in self.categories],
            'articles': [article.to_dict() for article in self.articles],
        }
