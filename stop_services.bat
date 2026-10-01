@echo off
title Plove 4.0 一键停止服务
echo 正在停止 Plove 4.0 端口占用 (4000, 4001, 8088)...

powershell -NoProfile -Command ^
  "Get-NetTCPConnection | Where-Object { $_.LocalPort -in 4000, 4001, 8088 -and $_.OwningProcess -gt 0 } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo 全部服务已停止。
pause
