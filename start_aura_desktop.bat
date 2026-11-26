@echo off
title AURA Live Desktop Companion
cd /d "%~dp0"

echo ========================================================
echo   AURA Live Desktop Companion
echo   Local STT + Vision LLM + Streaming TTS + Live2D/3D
echo ========================================================

:: Clean up any previous desktop-agent on port 8765
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765 ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)

if not exist "desktop-agent\.venv\Scripts\python.exe" (
  echo [ERROR] Python virtualenv not found at desktop-agent\.venv
  echo Create it first:
  echo   cd desktop-agent ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "desktop\node_modules" (
  echo [INFO] Installing desktop dependencies...
  pushd desktop
  call npm install --legacy-peer-deps
  popd
)

echo [1/2] Starting AURA Desktop Agent (http://127.0.0.1:8765)...
start "AURA Desktop Agent" /min cmd /c "cd /d "%~dp0desktop-agent" && .venv\Scripts\python.exe main.py"

timeout /t 2 /nobreak >nul

echo [2/2] Launching AURA Desktop Overlay...
pushd desktop
call npm run dev
popd
