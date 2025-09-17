#!/bin/bash
# kintone-scraper 环境设置脚本 (Linux/macOS)
# 防止多用户虚拟环境冲突的自动化脚本

set -e  # 遇到错误时退出

echo "🚀 kintone-scraper 环境设置脚本 (Linux/macOS)"
echo "解决多用户环境冲突问题"
echo "=================================================="

# 检查 Poetry 是否安装
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry 未安装，请先安装 Poetry: https://python-poetry.org/docs/#installation"
    exit 1
else
    echo "✅ Poetry 已安装"
fi

# 步骤1：清理可能存在的项目虚拟环境
echo ""
echo "步骤1：清理项目虚拟环境..."
if [ -d ".venv" ]; then
    echo "发现 .venv 目录，正在删除..."
    rm -rf .venv
    echo "✅ .venv 目录已删除"
else
    echo "✅ 未发现 .venv 目录"
fi

# 步骤2：清理 Poetry 虚拟环境缓存
echo ""
echo "步骤2：清理 Poetry 虚拟环境缓存..."
poetry env remove --all 2>/dev/null || true
echo "✅ Poetry 虚拟环境缓存已清理"

# 步骤3：配置 Poetry 虚拟环境策略
echo ""
echo "步骤3：配置 Poetry 虚拟环境策略..."
poetry config virtualenvs.in-project false
echo "✅ Poetry 配置更新：virtualenvs.in-project = false"

# 步骤4：验证配置
echo ""
echo "步骤4：验证配置..."
config=$(poetry config virtualenvs.in-project)
echo "当前配置：virtualenvs.in-project = $config"

if [ "$config" = "false" ]; then
    echo "✅ 配置正确"
else
    echo "❌ 配置异常，请手动运行：poetry config virtualenvs.in-project false"
    exit 1
fi

# 步骤5：安装依赖
echo ""
echo "步骤5：安装项目依赖..."
poetry install

if [ $? -eq 0 ]; then
    echo "✅ 依赖安装成功"
else
    echo "❌ 依赖安装失败"
    exit 1
fi

# 步骤5.1：安装后再次检查并清理.venv（Poetry有时会短暂创建）
echo ""
echo "步骤5.1：安装后清理检查..."
if [ -d ".venv" ]; then
    echo "发现Poetry安装时创建的.venv目录，正在删除..."
    rm -rf .venv
    echo "✅ 安装后清理完成"
else
    echo "✅ 没有发现.venv目录"
fi

# 步骤6：验证环境
echo ""
echo "步骤6：验证环境..."
poetry run python -c "import requests; print('✅ Python环境正常')"

if [ $? -eq 0 ]; then
    echo "✅ 环境验证成功"
else
    echo "❌ 环境验证失败"
    exit 1
fi

# 步骤7：显示虚拟环境信息
echo ""
echo "步骤7：虚拟环境信息..."
echo "虚拟环境位置："
poetry env list --full-path

echo ""
echo "🎉 环境设置完成！"
echo "=================================================="
echo "现在可以运行项目了："
echo "poetry run python scripts/run_scraper.py tiny --use-api --skip-external-images"
echo ""
echo "⚠️  重要提示："
echo "• 每个协作者都应该运行这个脚本来避免环境冲突"
echo "• 不要在项目目录创建 .venv 目录"
echo "• 如果遇到问题，重新运行此脚本即可"
