# 测试文档

本目录包含kintone-scraper项目的所有测试文件。

## 目录结构

```
tests/
├── unit/                   # 单元测试
│   ├── test_models.py     # 数据模型测试
│   ├── test_utils.py      # 工具函数测试
│   ├── test_config.py     # 配置模块测试
│   └── test_scraper.py    # 抓取器单元测试
├── integration/            # 集成测试
│   ├── test_improved_scraper.py    # 抓取器集成测试
│   └── test_image_downloader.py   # 图片下载集成测试
├── manual/                 # 手动测试脚本
│   ├── quick_site_check.py        # 网站快速检查
│   ├── test_article_extraction.py # 文章提取测试
│   ├── test_section_detailed.py   # Section详细测试
│   └── test_section.py            # Section基础测试
├── fixtures/               # 测试数据和固定装置
│   └── sample_data.py     # 示例数据
├── conftest.py            # pytest配置
└── README.md              # 本文档
```

## 运行测试

### 运行所有测试
```bash
poetry run pytest
```

### 运行特定类型的测试
```bash
# 只运行单元测试
poetry run pytest -m unit

# 只运行集成测试
poetry run pytest -m integration

# 排除慢速测试
poetry run pytest -m "not slow"
```

### 运行特定文件的测试
```bash
# 运行模型测试
poetry run pytest tests/unit/test_models.py

# 运行抓取器测试
poetry run pytest tests/unit/test_scraper.py -v
```

### 查看测试覆盖率
```bash
poetry run pytest --cov=kintone_scraper --cov-report=html
```

## 手动测试脚本

`manual/` 目录下的脚本用于手动验证功能，不是自动化测试：

### 网站结构检查
```bash
poetry run python tests/manual/quick_site_check.py
```

### 文章提取测试
```bash
poetry run python tests/manual/test_article_extraction.py
```

### Section页面详细测试
```bash
poetry run python tests/manual/test_section_detailed.py
```

## 测试标记

- `unit`: 单元测试，快速执行，不依赖外部资源
- `integration`: 集成测试，可能较慢，测试组件间交互
- `slow`: 慢速测试，通常是网络请求或大量数据处理
- `manual`: 手动测试脚本，不在自动化测试中运行

## 编写新测试

### 单元测试
- 放在 `unit/` 目录下
- 文件名以 `test_` 开头
- 测试单个函数或类的功能
- 使用mock避免外部依赖

### 集成测试
- 放在 `integration/` 目录下
- 测试多个组件的交互
- 可以使用真实的网络请求（但要控制频率）

### 测试数据
- 共享的测试数据放在 `fixtures/sample_data.py`
- 使用pytest fixture提供测试数据
- 避免硬编码测试数据

## 最佳实践

1. **测试命名**: 使用描述性的测试名称，说明测试的功能
2. **测试隔离**: 每个测试应该独立，不依赖其他测试的状态
3. **使用fixture**: 利用pytest fixture提供测试数据和环境
4. **模拟外部依赖**: 使用mock模拟网络请求、文件操作等
5. **断言明确**: 使用具体的断言，而不是简单的True/False
6. **测试边界情况**: 包括正常情况、边界值和异常情况

## 常见问题

### 测试运行缓慢
- 使用 `-m "not slow"` 排除慢速测试
- 检查是否有不必要的网络请求
- 考虑使用mock替代真实请求

### 测试失败
- 检查网络连接
- 确认测试数据是否有效
- 查看详细的错误信息 (`pytest -v`)

### 添加新的测试依赖
```bash
poetry add --group dev pytest-mock pytest-asyncio
```

