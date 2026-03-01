@echo off
title AURA Launcher
echo +--------------------------------------+
echo I        AURA System Launcher          I
echo I     Zero-Docker Architecture         I
echo +--------------------------------------+
echo.

:: ─── Cleanup Existing Services ──────────────
echo Cleaning up existing AURA services...
taskkill /F /FI "WINDOWTITLE eq AURA Token Server" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AURA Voice Agent" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AURA AI Service" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AURA Dashboard" /T >nul 2>&1
timeout /t 1 /nobreak >nul

:: ─── 0. Setup Virtual Environments ──────────
echo [0/4] Checking environments...

:: AI Service
if not exist "ai-service\venv" (
    echo Creating AI Service venv...
    python -m venv ai-service\venv
)
echo Installing/Updating AI Service dependencies...
call ai-service\venv\Scripts\activate
pip install -r ai-service\requirements.txt
call deactivate

:: Voice Agent
if not exist "voice-agent\venv" (
    echo Creating Voice Agent venv...
    python -m venv voice-agent\venv
)
echo Installing/Updating Voice Agent dependencies...
call voice-agent\venv\Scripts\activate
pip install -r voice-agent\requirements.txt
call deactivate

echo.
echo Environments ready. Starting services...
echo.

:: ─── 1. Token Server ────────────────────────
echo [1/4] Starting Token Server (port 8082)...
start "AURA Token Server" cmd /k "cd voice-agent & venv\Scripts\activate & python token_server.py"
timeout /t 2 /nobreak >nul

:: ─── 2. Voice Agent (handles local Qwen or Cloud TTS) ───
echo [2/4] Starting Voice Agent...

:: Parse TTS_TYPE from .env
set "TTS_TYPE=qwen"
for /f "tokens=2 delims==" %%a in ('findstr /I "^TTS_TYPE=" ".env"') do set "TTS_TYPE=%%a"

if /I "%TTS_TYPE%"=="qwen" (
    echo Detect TTS_TYPE=qwen. Verifying 'aura' conda environment...
    call conda env list | findstr /R "\<aura\>" >nul
    if %errorlevel% neq 0 (
        echo [ERROR] Conda environment 'aura' not found!
        echo Since you have TTS_TYPE=qwen, this environment is REQUIRED for GPU acceleration.
        echo Please run: conda env create -f voice-agent\environment.yml
        echo Or change TTS_TYPE=cartesia in .env to use cloud TTS.
        echo.
        pause
        exit /b 1
    )
    start "AURA Voice Agent" cmd /k "cd voice-agent & conda activate aura & python agent.py dev"
) else (
    echo Detect TTS_TYPE=%TTS_TYPE% (Cloud). Using standard venv...
    start "AURA Voice Agent" cmd /k "cd voice-agent & venv\Scripts\activate & python agent.py dev"
)
timeout /t 2 /nobreak >nul

:: ─── 3. AI Service (direct) ──────
echo [3/4] Starting AI Service (port 8000)...
start "AURA AI Service" cmd /k "cd ai-service & venv\Scripts\activate & python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 /nobreak >nul

:: ─── 4. Dashboard ───────────────────────────
echo [4/4] Starting Dashboard (port 5173)...
start "AURA Dashboard" cmd /k "cd dashboard & npm run dev -- --host"
timeout /t 5 /nobreak >nul

:: ─── Open browser ───────────────────────────
@REM start http://localhost:5173

echo.
echo All services running! Close this window or CTRL+C to stop.
pause
