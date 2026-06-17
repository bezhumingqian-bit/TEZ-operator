@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ===================================================================
:: TEZ Operator - 内网访问开通脚本（OpenClaw 云桌面）
:: 作用：1) 放行 Windows 防火墙 8000 端口（入站）
::       2) 打印本机内网 IP 和同事可访问的地址
:: 用法：右键“以管理员身份运行”，或在管理员 CMD 执行
:: ===================================================================

echo ===================================================================
echo   TEZ Operator - 开通内网访问
echo ===================================================================
echo.

:: ---------- 1. 检查管理员权限 ----------
net session >nul 2>&1
if errorlevel 1 (
    echo [X] 需要管理员权限才能修改防火墙！
    echo     请关闭本窗口，右键此脚本 -^> “以管理员身份运行”
    echo.
    pause
    exit /b 1
)
echo [1/3] 管理员权限 OK
echo.

:: ---------- 2. 放行防火墙 8000 端口 ----------
echo [2/3] 配置 Windows 防火墙（放行 TCP 8000 入站）...
:: 先删旧规则避免重复堆叠（忽略不存在的报错）
netsh advfirewall firewall delete rule name="TEZ Operator 8000" >nul 2>&1
netsh advfirewall firewall add rule name="TEZ Operator 8000" dir=in action=allow protocol=TCP localport=8000 >nul
if errorlevel 1 (
    echo [X] 防火墙规则添加失败
    pause
    exit /b 1
)
echo [=] 已放行 8000 端口入站
echo.

:: ---------- 3. 获取本机内网 IPv4 ----------
:: 注意：PowerShell 命令必须直接执行，不能套在 for /f('...') 的单引号里，
:: 否则管道符 | 和花括号 {} 会被 cmd 错误解析（曾导致 Where-Object 报错）。
echo [3/3] 本机内网 IP 地址（把 9.x 或 10.x 开头的发给同事）：
echo -------------------------------------------------------------------
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' } | ForEach-Object { '   http://' + $_.IPAddress + ':8000' }"
echo -------------------------------------------------------------------
echo.
echo ===================================================================
echo   把上面 9.x 或 10.x 开头的地址发给同事即可访问（同一内网）。
echo ===================================================================
echo.
echo 提示：如果同事仍访问不到，多半是云桌面平台做了网络隔离，
echo       需联系 OpenClaw 平台管理员开放互访，或换内网普通机器部署。
echo.
pause
endlocal
