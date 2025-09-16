# kintone-scraper

kintone开发者文档抓取器 - 自动抓取并整理cybozu开发者网站的所有技术文档

## 🌟 功能特性

- ✅ **智能分类抓取**: 按照网站的目录层级自动组织下载的文档
- ✅ **完整内容提取**: 抓取文章标题、内容、分类、更新时间等完整信息
- ✅ **离线HTML版本**: 生成带导航的完整离线HTML文档网站
- ✅ **图片和附件下载**: 自动下载文章中的图片和附件文件
- ✅ **智能链接处理**: 文章间链接自动转换为本地链接，外部链接保持可用
- ✅ **分类筛选界面**: 支持树状分类导航和文章筛选功能
- ✅ **多模式运行**: 支持测试、小批量、全量三种抓取模式，输出目录分离
- ✅ **友好抓取**: 自动控制请求频率，避免对服务器造成压力
- ✅ **进度跟踪**: 实时显示抓取进度和统计信息

## 📁 项目结构

```
kintone-scraper/
├── src/
│   └── kintone_scraper/
│       ├── __init__.py
│       ├── cli.py              # 命令行接口
│       ├── scraper.py          # 核心抓取器
│       ├── image_downloader.py # 图片和附件下载器
│       ├── models.py           # 数据模型
│       ├── utils.py            # 工具函数
│       └── config.py           # 配置文件
├── scripts/
│   └── run_scraper.py          # 主运行脚本
├── tests/                      # 单元测试和集成测试
├── output/                     # 完整抓取输出（保留）
├── output_test/                # 测试模式输出
├── output_small/               # 小批量模式输出
├── output_full/                # 全量模式输出
├── pyproject.toml             # Poetry配置
├── README.md                  # 项目说明
└── pytest.ini                # 测试配置
```

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd kintone-scraper

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell
```

### 使用方法

项目支持三种运行模式：测试、小批量、全量抓取。**每种模式会自动创建独立的输出目录，避免相互覆盖。**

```bash
# 测试模式 - 只抓取少量文章验证功能
# 输出目录: output_test/
poetry run python scripts/run_scraper.py test

# 小批量模式 - 抓取部分文档  
# 输出目录: output_small/
poetry run python scripts/run_scraper.py small

# 全量模式 - 抓取所有文档
# 输出目录: output_full/
poetry run python scripts/run_scraper.py full

# 指定输出目录（会在指定目录下创建模式子目录）
# 例如: ./my_data/test/, ./my_data/small/, ./my_data/full/
poetry run python scripts/run_scraper.py test -o ./my_data

# 尝试下载外部图片和附件（默认跳过）
poetry run python scripts/run_scraper.py test --try-external-images

# 查看帮助
poetry run python scripts/run_scraper.py --help
```

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

#### Markdown文件
每篇文章都会生成一个Markdown文件，包含：
- 文章标题
- 分类信息
- 最后更新时间
- 原文链接
- 完整内容

#### JSON数据
同时生成JSON格式的结构化数据：
- `complete_data.json` - 完整的抓取数据
- `articles_index.json` - 文章索引
- `categories.json` - 分类结构

## ⚙️ 配置选项

可以通过配置文件或命令行参数自定义抓取行为：

```python
# config.py
BASE_URL = "https://cybozudev.kf5.com/hc/"
REQUEST_DELAY = 0.5  # 请求间隔（秒）
TIMEOUT = 30         # 请求超时时间
MAX_RETRIES = 3      # 最大重试次数
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

欢迎提交Issue和Pull Request！

## ⚠️ 注意事项

- 请遵守网站的robots.txt和使用条款
- 建议在非高峰期运行，避免对服务器造成过大压力
- 如果网站结构发生变化，可能需要更新选择器配置

## 🎯 项目状态

**当前版本**: 功能完善版本 ✨

- ✅ 核心抓取功能完整
- ✅ HTML离线版本支持
- ✅ 图片和附件下载
- ✅ 智能链接处理
- ✅ 分类导航界面
- ✅ 多模式运行支持
- ✅ 完整的用户文档

项目已经过充分测试，可以稳定运行。所有主要功能都已实现并经过验证。

## 📞 联系方式

如有问题或建议，请提交Issue或联系维护者。

