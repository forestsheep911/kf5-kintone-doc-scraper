# kintone-scraper

kintone 开发者文档抓取器 - 自动抓取并整理 cybozu 开发者网站的所有技术文档

## 🌟 功能特性

- ✅ **智能分类抓取**: 按照网站的目录层级自动组织下载的文档
- ✅ **完整内容提取**: 抓取文章标题、内容、分类、更新时间等完整信息
- ✅ **离线 HTML 版本**: 生成带导航的完整离线 HTML 文档网站
- ✅ **图片和附件下载**: 自动下载文章中的图片和附件文件
- ✅ **智能链接处理**: 文章间链接自动转换为本地链接，外部链接保持可用
- ✅ **分类筛选界面**: 支持树状分类导航和文章筛选功能
- ✅ **多模式运行**: 支持测试、小批量、全量三种抓取模式，输出目录分离
- ✅ **友好抓取**: 自动控制请求频率，避免对服务器造成压力
- ✅ **进度跟踪**: 实时显示抓取进度和统计信息
- ✅ **多线程并发**: 支持可配置的多线程抓取，提升效率
- ✅ **KF5 API 集成**: 支持 API 驱动的抓取模式，更完整不易漏文
- ✅ **智能跳过**: 自动跳过已抓取文章，支持增量更新

## 📁 项目结构

```
kintone-scraper/
├── src/
│   └── kintone_scraper/
│       ├── __init__.py
│       ├── cli.py              # 命令行接口
│       ├── scraper.py          # 核心抓取器
│       ├── image_downloader.py # 图片和附件下载器
│       ├── kf5_api.py          # KF5 API客户端（可选）
│       ├── models.py           # 数据模型
│       ├── utils.py            # 工具函数
│       └── config.py           # 配置文件
├── scripts/
│   ├── run_scraper.py          # 主运行脚本
│   ├── inject_copy_buttons.py  # HTML复制按钮注入
│   └── ...                     # 其他辅助脚本
├── config/
│   └── kf5_api.toml            # KF5 API配置（可选）
├── tests/                      # 单元测试和集成测试
├── output/                     # 完整抓取输出（保留）
├── output_test/                # 测试模式输出
├── output_small/               # 小批量模式输出
├── output_tiny/                # 微型模式输出
├── output_full/                # 全量模式输出
├── setup_env.ps1               # 环境设置脚本（Windows）
├── setup_env.sh                # 环境设置脚本（Linux/macOS）
├── pyproject.toml              # Poetry配置
├── README.md                   # 项目说明
└── pytest.ini                 # 测试配置
```

## 🚀 快速开始

### 安装

#### 🚀 推荐方式（自动化）

**Windows PowerShell 用户**：

```powershell
# 克隆项目
git clone <repository-url>
cd kintone-scraper

# 运行自动化环境设置脚本（推荐）
.\setup_env.ps1
```

**Linux/macOS 用户**：

```bash
# 克隆项目
git clone <repository-url>
cd kintone-scraper

# 运行自动化环境设置脚本（推荐）
chmod +x setup_env.sh
./setup_env.sh
```

#### 📖 手动方式

```bash
# 克隆项目
git clone <repository-url>
cd kintone-scraper

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell
```

> ⚠️ **多用户协作注意事项**：
>
> - **所有协作者都必须运行 `poetry config virtualenvs.in-project false`**
> - 这样可以防止不同操作系统间的虚拟环境冲突
> - 如果项目中出现 `.venv` 目录，说明有人没有正确配置

### 使用方法

项目支持四种运行模式：测试、微型、小批量、全量抓取。**每种模式会自动创建独立的输出目录，避免相互覆盖。**

#### 基础命令

```bash
# 测试模式 - 抓取2个section的少量文章验证功能
# 输出目录: output_test/
poetry run python scripts/run_scraper.py test

# 微型模式 - 每个分类抓取1篇文章（快速测试用）
# 输出目录: output_tiny/
poetry run python scripts/run_scraper.py tiny

# 小批量模式 - 每个分类抓取至多3篇文章
# 输出目录: output_small/
poetry run python scripts/run_scraper.py small

# 全量模式 - 抓取所有文档
# 输出目录: output_full/
poetry run python scripts/run_scraper.py full
```

#### API 驱动模式（推荐）

使用 KF5 API 获取文章列表，更完整不易漏文：

```bash
# 微型模式（API驱动）- 测试API模式的分类逻辑
poetry run python scripts/run_scraper.py tiny --use-api

# 小批量模式（API驱动）- 每个分类抓取至多3篇文章
poetry run python scripts/run_scraper.py small --use-api

# 全量模式（API驱动）- 抓取所有文档
poetry run python scripts/run_scraper.py full --use-api
```

#### 常用参数组合

```bash
# 指定输出目录（会在指定目录下创建模式子目录）
# 例如: ./my_data/tiny/, ./my_data/small/, ./my_data/full/
poetry run python scripts/run_scraper.py tiny -o ./my_data

# 跳过外部图片和附件下载（提升速度）
poetry run python scripts/run_scraper.py small --skip-external-images

# 强制重新下载已存在的文章（不跳过）
poetry run python scripts/run_scraper.py small --no-skip-existing

# 组合使用：API模式 + 跳过外部图片 + 指定目录
poetry run python scripts/run_scraper.py tiny --use-api --skip-external-images -o ./output

# 查看所有可用参数
poetry run python scripts/run_scraper.py --help
```

#### 运行模式对比

| 模式    | 抓取量                    | 推荐用途           | 时间估计       | 输出目录        |
| ------- | ------------------------- | ------------------ | -------------- | --------------- |
| `test`  | 2 个 section，每个 2-5 篇 | 功能验证，新手尝试 | 1-2 分钟       | `output_test/`  |
| `tiny`  | 每个分类 1 篇文章         | 快速测试，结构预览 | 2-5 分钟       | `output_tiny/`  |
| `small` | 每个分类至多 3 篇文章     | 内容预览，质量评估 | 5-15 分钟      | `output_small/` |
| `full`  | 所有文章                  | 完整归档，生产使用 | 30 分钟-数小时 | `output_full/`  |

> **提示**:
>
> - 小批量/微型模式会显示未抓取文章列表，方便后续补抓
> - API 模式（`--use-api`）通常更快且更完整
> - 少量 403/404 错误是正常的（某些文章确实无法访问）

### Python API

```python
from kintone_scraper import KintoneScraper

# 创建抓取器
scraper = KintoneScraper(output_dir="./data")

# 开始抓取
scraper.scrape_all()

# 或者只抓取特定分类
scraper.scrape_categories(["API文档", "插件"])
```

## 📊 输出格式

### 目录结构

不同运行模式会创建独立的输出目录，抓取的文档会按照网站的分类层级进行组织：

```
output_test/          # 测试模式输出
├── html/            # HTML格式文档
├── images/          # 下载的图片
├── attachments/     # 下载的附件
└── scraper.log     # 运行日志

output_small/         # 小批量模式输出
├── html/
│   ├── index.html   # 主页面（支持分类筛选）
│   ├── API文档/
│   │   └── kintone REST API/
│   │       ├── 200733_kintone REST API共通规格.html
│   │       └── ...
│   ├── 插件/
│   │   └── 插件开发/
│   └── 新手教程/
├── images/          # 图片文件
├── attachments/     # 附件文件
└── scraper.log

output_full/          # 全量模式输出（完整文档）
├── html/            # 所有HTML文档
├── images/          # 所有图片
├── attachments/     # 所有附件
└── scraper.log
```

### 文件格式

#### Markdown 文件

每篇文章都会生成一个 Markdown 文件，包含：

- 文章标题
- 分类信息
- 最后更新时间
- 原文链接
- 完整内容

#### JSON 数据

同时生成 JSON 格式的结构化数据：

- `complete_data.json` - 完整的抓取数据
- `articles_index.json` - 文章索引
- `categories.json` - 分类结构

## ⚙️ 配置选项

### 命令行参数

主运行脚本 `scripts/run_scraper.py` 支持的参数：

| 参数                     | 说明                                   | 示例                     |
| ------------------------ | -------------------------------------- | ------------------------ |
| `mode`                   | 运行模式：`test`/`tiny`/`small`/`full` | `tiny`                   |
| `-o, --output`           | 输出目录（默认：output）               | `-o ./my_data`           |
| `--use-api`              | 使用 KF5 API 模式（推荐）              | `--use-api`              |
| `--skip-external-images` | 跳过外部图片下载                       | `--skip-external-images` |
| `--no-skip-existing`     | 不跳过已存在文章                       | `--no-skip-existing`     |

### 核心配置参数

可以通过修改 `src/kintone_scraper/config.py` 自定义抓取行为：

```python
# 网络配置
BASE_URL = "https://cybozudev.kf5.com/hc/"
REQUEST_TIMEOUT = 30        # 请求超时时间（秒）
REQUEST_DELAY = 0.5         # 请求间隔（秒）
MAX_RETRIES = 3             # 最大重试次数

# 并发配置
ARTICLE_WORKERS = 4         # 文章抓取并发线程数
BATCH_SIZE = 10             # 每批处理的文章数量

# 用户代理
USER_AGENT = "Mozilla/5.0 ..."
```

### Python API 配置

```python
from kintone_scraper import KintoneScraper

# 创建抓取器并配置参数
scraper = KintoneScraper(
    output_dir="./data",           # 输出目录
    base_url="https://...",        # 基础URL
    enable_images=True,            # 启用图片下载
    try_external_images=True,      # 尝试下载外部图片
    skip_existing=True,            # 跳过已存在文章
    article_workers=4              # 并发线程数
)

# 开始抓取
scraper.scrape_all()

# 或者只抓取特定分类
scraper.scrape_categories(["API文档", "插件"])
```

## 🧪 测试

```bash
# 运行所有测试
poetry run pytest

# 运行特定测试
poetry run pytest tests/test_scraper.py

# 查看测试覆盖率
poetry run pytest --cov=kintone_scraper
```

## 📝 开发

### 代码格式化

```bash
# 格式化代码
poetry run black src/ tests/
poetry run isort src/ tests/

# 类型检查
poetry run mypy src/
```

### 添加新功能

1. 在 `src/kintone_scraper/` 下添加新模块
2. 编写相应的测试
3. 更新文档

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## ⚠️ 注意事项

- 请遵守网站的 robots.txt 和使用条款
- 建议在非高峰期运行，避免对服务器造成过大压力
- 如果网站结构发生变化，可能需要更新选择器配置
- API 模式需要配置 KF5 访问凭据（可选，网页模式也能工作）

## 🛠️ 故障排除

### 虚拟环境问题

**问题**: `ModuleNotFoundError: No module named 'requests'` 或 `virtual environment seems to be broken`

**原因**: 多人共用虚拟环境，不同操作系统（WSL vs PowerShell vs Linux）之间冲突。

**解决方案**:

```powershell
# Windows PowerShell 环境：
# 1. 删除项目中的损坏虚拟环境
Remove-Item -Path ".venv" -Recurse -Force -ErrorAction SilentlyContinue

# 2. 清理Poetry虚拟环境缓存
poetry env remove --all

# 3. 配置Poetry不在项目目录创建虚拟环境（关键步骤！）
poetry config virtualenvs.in-project false

# 4. 重新安装依赖
poetry install

# 5. 验证安装
poetry run python -c "import requests; print('✅ 环境修复成功')"
```

```bash
# Linux/macOS 环境：
# 执行相同的步骤（命令语法稍有不同）
rm -rf .venv
poetry env remove --all
poetry config virtualenvs.in-project false
poetry install
```

### 网络连接问题

**问题**: 连接超时或 403 错误

**解决方案**:

- 检查网络连接
- 尝试更换网络环境
- 增加 `REQUEST_DELAY` 值减缓请求频率
- 某些文章可能确实无法访问（403/404 是正常的）

### API 配置问题

**问题**: 使用 `--use-api` 时提示 "KF5 API 未配置"

**解决方案**:

1. 检查 `config/kf5_api.toml` 配置文件
2. 如果没有 API 访问权限，不使用 `--use-api` 参数（默认网页模式）

### 性能优化建议

**抓取速度慢**:

- 使用 `--skip-external-images` 跳过外部图片
- 增加 `ARTICLE_WORKERS` 线程数（注意不要过高）
- 使用 `--use-api` 模式（通常更快）

**内存使用过高**:

- 减少 `ARTICLE_WORKERS` 线程数
- 使用小批量模式而不是全量模式
- 定期清理输出目录中的旧文件

## 🎯 项目状态

**当前版本**: 功能完善版本 ✨

- ✅ 核心抓取功能完整
- ✅ HTML 离线版本支持
- ✅ 图片和附件下载
- ✅ 智能链接处理
- ✅ 分类导航界面
- ✅ 多模式运行支持
- ✅ 多线程并发抓取
- ✅ KF5 API 集成支持
- ✅ 完整的用户文档
- ✅ 跨平台兼容性

项目已经过充分测试，可以稳定运行。所有主要功能都已实现并经过验证。

## 📞 联系方式

如有问题或建议，请提交 Issue 或联系维护者。
