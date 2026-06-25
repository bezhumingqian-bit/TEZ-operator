@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ===================================================================
:: TEZ Operator - 内网访问开通脚本（VDI 云桌面）
:: 作用：1) 放行 Windows 防火墙 80 端口（入站）
::       2) 打印本机内网 IP 和同事可访问的地址
:: 用法：右键"以管理员身份运行"，或在管理员 CMD 执行
:: 注意：VDI 出口 ACL 只放行标准端口（80/443），因此服务用 80 端口。
:: ===================================================================

echo ===================================================================
echo   TEZ Operator - 开通内网访问（80 端口）
echo ===================================================================
echo.

:: ---------- 1. 检查管理员权限 ----------
net session >nul 2>&1
if errorlevel 1 (
    echo [X] 需要管理员权限才能修改防火墙！
    echo     请关闭本窗口，右键此脚本 -^> "以管理员身份运行"
    echo.
    pause
    exit /b 1
)
echo [1/3] 管理员权限 OK
echo.

:: ---------- 2. 放行防火墙 80 端口 ----------
echo [2/3] 配置 Windows 防火墙（放行 TCP 80 入站）...
:: 先删旧规则避免重复堆叠（忽略不存在的报错）
netsh advfirewall firewall delete rule name="TEZ Operator 80" >nul 2>&1
netsh advfirewall firewall add rule name="TEZ Operator 80" dir=in action=allow protocol=TCP localport=80 >nul
if errorlevel 1 (
    echo [X] 防火墙规则添加失败
    pause
    exit /b 1
)
echo [=] 已放行 80 端口入站
echo.

:: ---------- 3. 获取本机内网 IPv4 ----------
echo [3/3] 本机内网 IP 地址（发给同事即可访问，标准 HTTP 端口无需加 :80）：
echo -------------------------------------------------------------------
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' } | ForEach-Object { '   http://' + $_.IPAddress }"
echo -------------------------------------------------------------------
echo.
echo ===================================================================
echo   直接把上面的地址发给同事即可访问（VDI ACL 放行标准端口）。
echo ===================================================================
echo.
echo 提示：如果同事仍访问不到，可能是集团安全策略限制，
echo       本机使用 http://localhost 访问不受影响。
echo.
pause
endlocal
