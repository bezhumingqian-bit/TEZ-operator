# TEZ Operator 云桌面一键部署脚本 (Windows)
# 用法：在云桌面上右键 → "使用 PowerShell 运行"，或：
#   powershell -ExecutionPolicy Bypass -File deploy_cloud_windows.ps1

$ErrorActionPreference = "Stop"
$ProjectDir = "$env:USERPROFILE\TEZ-operator"
$PythonVersion = "3.11"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TEZ Operator 云桌面部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: 检查 Python ──
Write-Host "[1/6] 检查 Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  Python 未安装，请先安装 Python 3.11：https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "  安装时勾选 'Add Python to PATH'" -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $($python.Source)" -ForegroundColor Green
python --version

# ── Step 2: 复制项目文件 ──
Write-Host "[2/6] 复制项目文件..." -ForegroundColor Yellow
if (Test-Path $ProjectDir) {
    Write-Host "  项目目录已存在，跳过复制" -ForegroundColor Gray
} else {
    Write-Host "  请先将 TEZ-operator 项目文件夹复制到 $ProjectDir" -ForegroundColor Yellow
    Write-Host "  （可以用 U盘、企业微信文件传输、或内网共享）" -ForegroundColor Yellow
    Write-Host "  复制完成后重新运行此脚本" -ForegroundColor Yellow
    exit 0
}

Set-Location $ProjectDir

# ── Step 3: 安装 Python 依赖 ──
Write-Host "[3/6] 安装 Python 依赖..." -ForegroundColor Yellow
pip install -r requirements.txt -q
Write-Host "  依赖安装完成" -ForegroundColor Green

# ── Step 4: 安装 Playwright 浏览器 ──
Write-Host "[4/6] 安装 Playwright Chromium..." -ForegroundColor Yellow
python -m playwright install chromium
Write-Host "  Chromium 安装完成" -ForegroundColor Green

# ── Step 5: 配置环境变量 ──
Write-Host "[5/6] 检查配置文件..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  未找到 .env 文件，请从项目源码复制" -ForegroundColor Red
    exit 1
}

# 确保云桌面使用有头浏览器（首次需要扫码登录）
$envContent = Get-Content .env -Raw
if ($envContent -match "TEZ_BROWSER_HEADLESS=true") {
    Write-Host "  将 headless 改为 false（云桌面需要可视化扫码）" -ForegroundColor Yellow
    (Get-Content .env) -replace "TEZ_BROWSER_HEADLESS=true", "TEZ_BROWSER_HEADLESS=false" | Set-Content .env
}
if ($envContent -match "TEZ_APP_DEBUG=true") {
    Write-Host "  将 debug 改为 false（生产环境）" -ForegroundColor Yellow
    (Get-Content .env) -replace "TEZ_APP_DEBUG=true", "TEZ_APP_DEBUG=false" | Set-Content .env
}
Write-Host "  配置检查完成" -ForegroundColor Green

# ── Step 6: 设置开机自启 ──
Write-Host "[6/6] 设置开机自启..." -ForegroundColor Yellow

$TaskName = "TEZ-Operator"
$TaskExists = schtasks /query /tn $TaskName 2>$null

if ($TaskExists) {
    Write-Host "  任务已存在，跳过" -ForegroundColor Gray
} else {
    $StartScript = @"
@echo off
cd /d $ProjectDir
python -m uvicorn app.main:app --host 0.0.0.0 --port 80 --log-level warning
"@
    $StartScriptPath = "$ProjectDir\start_tez.bat"
    $StartScript | Out-File -FilePath $StartScriptPath -Encoding ASCII

    schtasks /create /tn $TaskName /tr $StartScriptPath /sc onstart /delay 0000:30 /rl highest /f
    Write-Host "  开机自启已设置（任务名: $TaskName）" -ForegroundColor Green
}

# ── 完成 ──
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  下一步：" -ForegroundColor Yellow
Write-Host "  1. 启动服务：" -ForegroundColor White
Write-Host "     cd $ProjectDir" -ForegroundColor Gray
Write-Host "     python -m uvicorn app.main:app --host 0.0.0.0 --port 80" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. 首次登录：浏览器会弹窗 → 扫码登录 iOA" -ForegroundColor White
Write-Host "     （只需一次，cookie 会自动保存到 data/playwright-profile）" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. 访问地址：http://本机IP:80" -ForegroundColor White
Write-Host "     （查 IP: ipconfig）" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. 管理开机自启：" -ForegroundColor White
Write-Host "     查看: schtasks /query /tn TEZ-Operator" -ForegroundColor Gray
Write-Host "     删除: schtasks /delete /tn TEZ-Operator /f" -ForegroundColor Gray
Write-Host "     立即启动: schtasks /run /tn TEZ-Operator" -ForegroundColor Gray
