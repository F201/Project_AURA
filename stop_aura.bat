@echo off
title AURA Cleanup
echo +--------------------------------------+
echo I        AURA Cleanup Utility          I
echo +--------------------------------------+
echo.

echo Stopping AURA Voice Agent processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*agent.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Stopping AURA Token Server processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*token_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Stopping AURA AI Service (uvicorn) processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Stopping AURA Dashboard (vite/node) processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*vite*' -or $_.CommandLine -like '*npm run dev*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Stopping windows by title...
taskkill /F /FI "WINDOWTITLE eq AURA Token Server" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AURA Voice Agent" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AURA AI Service" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AURA Dashboard" /T >nul 2>&1

:: Force kill anything on ports 8000, 8001, 8082
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8082') do taskkill /F /PID %%a >nul 2>&1

echo.
echo All AURA services stopped.
timeout /t 2 /nobreak >nul
exit

