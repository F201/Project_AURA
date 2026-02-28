@echo off
title AURA Launcher
echo +--------------------------------------+
echo I        AURA System Launcher          I
echo I     Zero-Docker Architecture         I
echo +--------------------------------------+
echo.

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

:: ─── 2. Voice Agent (uses aura conda env for GPU-accelerated TTS) ───
echo [2/4] Starting Voice Agent...
start "AURA Voice Agent" cmd /k "cd voice-agent & conda activate aura & python agent.py dev"
timeout /t 2 /nobreak >nul

:: ─── 3. AI Service (direct) ──────
echo [3/4] Starting AI Service (port 8000)...
start "AURA AI Service" cmd /k "cd ai-service & venv\Scripts\activate & python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 /nobreak >nul

:: ─── 4. Dashboard ───────────────────────────
echo [4/4] Starting Dashboard (port 5173)...
start "AURA Dashboard" cmd /k "cd dashboard & npm run dev"
timeout /t 5 /nobreak >nul

:: ─── Open browser ───────────────────────────
@REM start http://localhost:5173

echo.
echo All services running! Close this window or CTRL+C to stop.
pause
