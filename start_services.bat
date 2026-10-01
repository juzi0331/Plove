@echo off
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ======================================================
echo   Plove 4.0 一键极速拉起三端服务
echo ======================================================
echo.

powershell -NoProfile -Command ^
  "$root = '%ROOT%'.TrimEnd('\'); " ^
  "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = \"$root\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 4001\"; CurrentDirectory = \"$root\backend\" } | Out-Null; " ^
  "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = \"$root\backend\.venv\Scripts\python.exe -m uvicorn crawler.service.main:app --host 127.0.0.1 --port 8088\"; CurrentDirectory = \"$root\" } | Out-Null; " ^
  "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'cmd.exe /c npm run dev'; CurrentDirectory = \"$root\frontend\" } | Out-Null; "

echo [1/3] 后端核心已启动: http://127.0.0.1:4001/
echo [2/3] 爬虫工坊已启动: http://127.0.0.1:8088/
echo [3/3] 前端服务已启动: http://127.0.0.1:4000/
echo.
echo - 服务直达总控: http://127.0.0.1:4001/
echo - 终端播放大厅: http://127.0.0.1:4000/
echo - 安全运维后台: http://127.0.0.1:4000/_manage (默认口令: admin)
echo.
pause
