# kintone-scraper 环境设置脚本
# 防止多用户虚拟环境冲突的自动化脚本

Write-Host "🚀 kintone-scraper 环境设置脚本" -ForegroundColor Green
Write-Host "解决多用户环境冲突问题" -ForegroundColor Green
Write-Host "=" * 50

# 检查 Poetry 是否安装
try {
    poetry --version | Out-Null
    Write-Host "✅ Poetry 已安装" -ForegroundColor Green
}
catch {
    Write-Host "❌ Poetry 未安装，请先安装 Poetry: https://python-poetry.org/docs/#installation" -ForegroundColor Red
    exit 1
}

# 步骤1：清理可能存在的项目虚拟环境
Write-Host ""
Write-Host "步骤1：清理项目虚拟环境..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "发现 .venv 目录，正在删除..." -ForegroundColor Red
    Remove-Item -Path ".venv" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ .venv 目录已删除" -ForegroundColor Green
}
else {
    Write-Host "✅ 未发现 .venv 目录" -ForegroundColor Green
}

# 步骤2：清理 Poetry 虚拟环境缓存
Write-Host ""
Write-Host "步骤2：清理 Poetry 虚拟环境缓存..." -ForegroundColor Yellow
poetry env remove --all 2>$null
Write-Host "✅ Poetry 虚拟环境缓存已清理" -ForegroundColor Green

# 步骤3：配置 Poetry 虚拟环境策略
Write-Host ""
Write-Host "步骤3：配置 Poetry 虚拟环境策略..." -ForegroundColor Yellow
poetry config virtualenvs.in-project false
Write-Host "✅ Poetry 配置更新：virtualenvs.in-project = false" -ForegroundColor Green

# 步骤4：验证配置
Write-Host ""
Write-Host "步骤4：验证配置..." -ForegroundColor Yellow
$config = poetry config virtualenvs.in-project
Write-Host "当前配置：virtualenvs.in-project = $config" -ForegroundColor Cyan

if ($config -eq "false") {
    Write-Host "✅ 配置正确" -ForegroundColor Green
}
else {
    Write-Host "❌ 配置异常，请手动运行：poetry config virtualenvs.in-project false" -ForegroundColor Red
    exit 1
}

# 步骤5：安装依赖
Write-Host ""
Write-Host "步骤5：安装项目依赖..." -ForegroundColor Yellow
poetry install

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 依赖安装成功" -ForegroundColor Green
}
else {
    Write-Host "❌ 依赖安装失败" -ForegroundColor Red
    exit 1
}

# 步骤5.1：安装后再次检查并清理.venv（Poetry有时会短暂创建）
Write-Host ""
Write-Host "步骤5.1：安装后清理检查..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "发现Poetry安装时创建的.venv目录，正在删除..." -ForegroundColor Red
    Remove-Item -Path ".venv" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ 安装后清理完成" -ForegroundColor Green
}
else {
    Write-Host "✅ 没有发现.venv目录" -ForegroundColor Green
}

# 步骤6：验证环境
Write-Host ""
Write-Host "步骤6：验证环境..." -ForegroundColor Yellow
poetry run python -c "import requests; print('✅ Python环境正常')"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 环境验证成功" -ForegroundColor Green
}
else {
    Write-Host "❌ 环境验证失败" -ForegroundColor Red
    exit 1
}

# 步骤7：显示虚拟环境信息
Write-Host ""
Write-Host "步骤7：虚拟环境信息..." -ForegroundColor Yellow
Write-Host "虚拟环境位置：" -ForegroundColor Cyan
poetry env list --full-path

Write-Host ""
Write-Host "🎉 环境设置完成！" -ForegroundColor Green
Write-Host "=" * 50
Write-Host "现在可以运行项目了：" -ForegroundColor Yellow
Write-Host "poetry run python scripts/run_scraper.py tiny --use-api --skip-external-images" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  重要提示：" -ForegroundColor Yellow
Write-Host "• 每个协作者都应该运行这个脚本来避免环境冲突" -ForegroundColor White
Write-Host "• 不要在项目目录创建 .venv 目录" -ForegroundColor White
Write-Host "• 如果遇到问题，重新运行此脚本即可" -ForegroundColor White
