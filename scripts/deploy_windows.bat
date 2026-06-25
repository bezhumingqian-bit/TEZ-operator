@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ===================================================================
:: TEZ Operator - Windows 一键部署脚本（OpenClaw 云桌面）
:: 用法：在项目根目录双击运行，或 CMD 执行  scripts\deploy_windows.bat
:: 作用：装依赖 -> 建配置 -> 装浏览器内核 -> 构建前端 -> 建库 -> 启动服务
:: 单台机器同时托管：后端 API + 前端 UI + 浏览器自动化（有 iOA）
:: ===================================================================

:: 切到项目根目录（脚本所在目录的上一级）
cd /d "%~dp0.."
echo [TEZ] 项目根目录: %CD%
echo.

:: ---------- 1. 环境检查 ----------
echo [1/7] 检查 Python / Node 环境...
where python >nul 2>nul
if errorlevel 1 (
    echo [X] 未找到 python，请先安装 Python 3.11+ 并加入 PATH: https://www.python.org/downloads/
    pause & exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
    echo [X] 未找到 node，请先安装 Node.js LTS 并加入 PATH: https://nodejs.org/
    pause & exit /b 1
)
python --version
node --version
echo.

:: ---------- 2. 生成 .env（若不存在） ----------
echo [2/7] 检查 .env 配置...
if exist ".env" (
    echo [=] .env 已存在，跳过生成（如需重置请手动删除后重跑）
) else (
    echo [+] 生成 .env，使用 SQLite + browser 模式 + headless=false（有图形界面，点击登录+手机确认）
    python -c "import secrets;k=secrets.token_urlsafe(48);s=secrets.token_urlsafe(24);open('.env','w',encoding='utf-8').write('\n'.join(['TEZ_APP_ENV=local','TEZ_APP_DEBUG=false','TEZ_APP_PORT=80','TEZ_DATABASE_URL=sqlite+pysqlite:///./data/tez_operator.db','TEZ_REDIS_URL=','TEZ_CMDB_MODE=browser','TEZ_TCUM_MODE=browser','TEZ_IDCRM_MODE=browser','TEZ_BROWSER_HEADLESS=false','TEZ_BROWSER_PROFILE_DIR=data/playwright-profile','TEZ_CMDB_BASE_URL=http://cmdb.woa.com','TEZ_TCUM_BASE_URL=http://tcum.woa.com','TEZ_IDCRM_BASE_URL=http://idcrm.woa.com','TEZ_YUNXIAO_BASE_URL=http://yunxiao.vstation.woa.com','TEZ_JWT_SECRET_KEY='+k,'TEZ_PASSWORD_SALT='+s,''])+'\n')"
    echo [=] .env 已生成
)
if not exist "data" mkdir data
echo.

:: ---------- 3. 安装后端依赖 ----------
echo [3/7] 安装后端依赖（pip install -r requirements.txt）...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 ( echo [X] pip 安装失败 & pause & exit /b 1 )
echo.

:: ---------- 4. 安装 Playwright Chromium 内核 ----------
echo [4/7] 安装 Playwright Chromium 内核...
python -m playwright install chromium
echo.

:: ---------- 5. 构建前端 ----------
echo [5/7] 构建前端（npm install + npm run build）...
pushd web
call npm install
if errorlevel 1 ( echo [X] npm install 失败 & popd & pause & exit /b 1 )
call npm run build
if errorlevel 1 ( echo [X] npm run build 失败 & popd & pause & exit /b 1 )
popd
echo.

:: ---------- 6. 初始化数据库 ----------
echo [6/7] 初始化数据库（alembic 迁移 + 默认 admin 账号）...
python -m alembic upgrade head
if errorlevel 1 ( echo [!] alembic 迁移失败/未配置，尝试用 init_users 直接建表... )
python scripts\init_users.py
echo.

:: ---------- 7. 启动服务 ----------
echo [7/7] 启动 TEZ Operator 服务（0.0.0.0:80）...
echo.
echo ===================================================================
echo   部署完成！服务即将启动
echo   本机访问 : http://localhost
echo   API 文档 : http://localhost/docs
echo   默认账号 : admin / admin123（首次登录后请修改）
echo   按 Ctrl+C 可停止服务
echo ===================================================================
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 80

endlocal
