"""工具函数"""

import json
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from .config import get_safe_filename


def create_directory_structure(base_path: Path, categories: List[str]) -> None:
    """创建目录结构"""
    for category in categories:
        category_path = base_path / category
        category_path.mkdir(parents=True, exist_ok=True)


def save_json(data: Any, filepath: Path) -> None:
    """保存JSON文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: Path) -> Any:
    """加载JSON文件"""
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_markdown(title: str, content: str, metadata: Dict[str, str], filepath: Path) -> None:
    """保存Markdown文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        # 写入标题
        f.write(f"# {title}\n\n")
        
        # 写入元数据
        if metadata:
            f.write("## 文档信息\n\n")
            for key, value in metadata.items():
                if value:
                    f.write(f"- **{key}**: {value}\n")
            f.write("\n---\n\n")
        
        # 写入内容
        f.write(content)


def clean_html_content(html_content: str) -> str:
    """清理HTML内容，移除脚本和样式"""
    # 移除script和style标签及其内容
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除HTML注释
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
    
    return html_content.strip()


def extract_domain(url: str) -> str:
    """提取域名"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def make_absolute_url(url: str, base_url: str) -> str:
    """转换为绝对URL"""
    return urljoin(base_url, url)


def rate_limit(delay: float = 0.5) -> None:
    """速率限制"""
    time.sleep(delay)


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"


def format_duration(seconds: float) -> str:
    """格式化持续时间"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def validate_url(url: str) -> bool:
    """验证URL格式"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """清理文件名，确保在文件系统中安全"""
    # 移除或替换不安全的字符
    filename = get_safe_filename(filename, max_length)
    
    # 如果文件名为空或只有扩展名，使用默认名称
    if not filename or filename.startswith('.'):
        filename = f"untitled{filename}"
    
    return filename


def get_category_path_from_url(url: str) -> str:
    """从URL提取分类路径"""
    # 从section URL中提取ID
    match = re.search(r'/hc/kb/section/(\d+)/', url)
    if match:
        section_id = match.group(1)
        # 这里可以根据section_id映射到具体的分类
        # 暂时返回通用路径
        return f"section_{section_id}"
    
    return "未分类"


def progress_bar(current: int, total: int, width: int = 50) -> str:
    """生成进度条"""
    if total == 0:
        return "[" + "=" * width + "] 100%"
    
    progress = current / total
    filled = int(width * progress)
    bar = "=" * filled + "-" * (width - filled)
    percentage = int(progress * 100)
    
    return f"[{bar}] {percentage}% ({current}/{total})"


def estimate_time_remaining(start_time: float, current: int, total: int) -> str:
    """估算剩余时间"""
    if current == 0 or total == 0:
        return "未知"
    
    elapsed = time.time() - start_time
    if elapsed == 0:  # 避免除零错误
        return "未知"
    
    rate = current / elapsed
    if rate == 0:
        return "未知"
    
    remaining = (total - current) / rate
    return format_duration(remaining)


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total: int, description: str = ""):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self.last_update = 0
    
    def update(self, increment: int = 1) -> None:
        """更新进度"""
        self.current += increment
        
        # 限制更新频率（每0.1秒最多更新一次）
        now = time.time()
        if now - self.last_update < 0.1:
            return
        
        self.last_update = now
        self._display_progress()

    def _display_progress(self) -> None:
        """显示进度（文本版）"""
        bar = progress_bar(self.current, self.total)
        remaining = estimate_time_remaining(self.start_time, self.current, self.total)
        print(f"\r{self.description} {bar} ETA: {remaining}", end="", flush=True)
        if self.current >= self.total:
            elapsed = format_duration(time.time() - self.start_time)
            print(f"\n完成，用时: {elapsed}")

    def finish(self) -> None:
        """结束并打印最终状态（文本版）"""
        self.current = self.total
        self._display_progress()


# 可选：更美观的进度条（使用 rich），保持与 ProgressTracker 相同接口
class RichProgressTracker:
    def __init__(self, total: int, description: str = ""):
        self.total = total
        self.description = description or "进度"
        self.current = 0
        self._using_rich = False
        try:
            from rich.console import Console  # type: ignore
            from rich.progress import (
                Progress, SpinnerColumn, TextColumn, BarColumn,
                TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
            )  # type: ignore
            self._console = Console()
            self._progress = Progress(
                SpinnerColumn(style="cyan"),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self._console,
                transient=True,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(self.description, total=self.total)
            self._using_rich = True
        except Exception:
            # 回退到文本进度
            self._using_rich = False
            self._fallback = SimpleTextProgress(total, description)

    def update(self, increment: int = 1) -> None:
        if self._using_rich:
            try:
                self.current += increment
                self._progress.update(self._task_id, advance=increment)
                if self.current >= self.total:
                    self._progress.stop()
            except Exception:
                self._using_rich = False
        else:
            self._fallback.update(increment)

    def finish(self) -> None:
        if self._using_rich:
            try:
                self._progress.update(self._task_id, completed=self.total)
                self._progress.stop()
            except Exception:
                pass
        else:
            self._fallback.finish()


def make_progress(total: int, description: str = "") -> ProgressTracker:
    """返回一个进度条实例，优先使用 rich，美观友好；失败回退到文本版。
    用法：tracker = make_progress(n, "抓取文章:"); tracker.update(); tracker.finish()
    """
    try:
        return RichProgressTracker(total, description)
    except Exception:
        return SimpleTextProgress(total, description)


class SimpleTextProgress:
    def __init__(self, total: int, description: str = ""):
        self.total = total
        self.description = description or "进度"
        self.current = 0
        self.start_time = time.time()
        self.last_update = 0.0

    def update(self, increment: int = 1) -> None:
        self.current += increment
        now = time.time()
        if now - self.last_update < 0.1:
            return
        self.last_update = now
        self._display()

    def _display(self) -> None:
        bar = progress_bar(self.current, self.total)
        remaining = estimate_time_remaining(self.start_time, self.current, self.total)
        print(f"\r{self.description} {bar} ETA: {remaining}", end="", flush=True)
        if self.current >= self.total:
            elapsed = format_duration(time.time() - self.start_time)
            print(f"\n完成，用时: {elapsed}")

    def finish(self) -> None:
        self.current = self.total
        self._display()



