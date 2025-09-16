# 使用手册

本项目用于抓取并离线构建 kintone 相关文档的本地站点，支持测试/小型/完整三种模式输出。

## 快速开始

1) 安装依赖

```bash
poetry install
poetry shell
```

2) 运行抓取（三选一）

```bash
# 测试模式（少量页面用于验证），输出到 output_test/
poetry run python scripts/run_scraper.py test

# 小型模式，输出到 output_small/
poetry run python scripts/run_scraper.py small

# 完整模式，输出到 output_full/
poetry run python scripts/run_scraper.py full
```

3) 本地浏览

打开对应输出目录的 `html/index.html`。

## 一键复制代码

- 已为所有文章页面注入复制按钮与样式，自动识别 `<pre><code>` 与常见语法高亮类名。
- 按钮显示在代码块右上角，点击即可复制到剪贴板；不支持 Clipboard API 的浏览器会自动回退。
- 如果后续新增页面或重新生成输出，可再次注入：

```bash
poetry run python scripts/inject_copy_buttons.py
# 或指定要处理的目录
poetry run python scripts/inject_copy_buttons.py ./output_full/html ./output/html
```

## 清理过时/临时产物

仓库保留了开发阶段的测试输出和缓存，可按需清理：

```bash
# 试运行（仅展示将删除的内容）
poetry run python scripts/cleanup_outputs.py

# 实际删除
poetry run python scripts/cleanup_outputs.py --apply

# 自定义额外路径/文件
poetry run python scripts/cleanup_outputs.py --apply --paths some/tmp --files tmp.txt
```

默认脚本会处理：`output_test/`、`output_small/`、`.pytest_cache/`、以及根目录旧的零散测试文件 `test_new_link_format.py`、`test_link_fixing.py`（若存在）。不会影响 `output_full/` 正式产物。

## 常用命令

```bash
# 查看帮助
poetry run python scripts/run_scraper.py --help

# 代码质量
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run flake8 src/

# 测试
poetry run pytest
```

