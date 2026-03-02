#!/usr/bin/env bash

echo "+--------------------------------------+"
echo "|        AURA System Launcher          |"
echo "|     Zero-Docker Architecture         |"
echo "+--------------------------------------+"
echo ""

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Cleanup Existing Services first
echo "Cleaning up existing AURA services..."
if [ -x "./stop_aura.sh" ]; then
    ./stop_aura.sh
elif [ -f "./stop_aura.sh" ]; then
    bash ./stop_aura.sh
fi
sleep 1

echo "[0/4] Checking environments..."

# AI Service
if [ ! -d "ai-service/venv" ]; then
    echo "Creating AI Service venv..."
    python3 -m venv ai-service/venv
fi
echo "Installing/Updating AI Service dependencies..."
source ai-service/venv/bin/activate || exit 1
pip install -r ai-service/requirements.txt
deactivate

# Voice Agent
if [ ! -d "voice-agent/venv" ]; then
    echo "Creating Voice Agent venv..."
    python3 -m venv voice-agent/venv
fi
echo "Installing/Updating Voice Agent dependencies..."
source voice-agent/venv/bin/activate || exit 1
pip install -r voice-agent/requirements.txt
deactivate

echo ""
echo "Environments ready. Starting services..."
echo ""

# Keep track of PIDs
PID_FILE=".aura_pids"
> "$PID_FILE"

# Make sure all children exit when this script exits
trap 'echo "Stopping services..."; bash ./stop_aura.sh; exit 0' INT TERM EXIT

# 1. Token Server
echo "[1/4] Starting Token Server (port 8082)..."
(
    cd voice-agent || exit
    source venv/bin/activate
    python token_server.py
) &
echo $! >> "$PID_FILE"
sleep 2

# 2. Voice Agent
echo "[2/4] Starting Voice Agent..."

TTS_TYPE="qwen"
if [ -f ".env" ]; then
    TTS_VAL=$(grep -i "^TTS_TYPE=" .env | cut -d '=' -f2 | tr -d '\r"' | xargs)
    if [ -n "$TTS_VAL" ]; then
        TTS_TYPE="$TTS_VAL"
    fi
fi

if [ "$(echo "$TTS_TYPE" | tr '[:upper:]' '[:lower:]')" = "qwen" ]; then
    echo "Detect TTS_TYPE=qwen. Verifying 'aura' conda environment..."
    if ! conda env list 2>/dev/null | grep -q "\baura\b"; then
        echo "[ERROR] Conda environment 'aura' not found!"
        echo "Since you have TTS_TYPE=qwen, this environment is REQUIRED for GPU acceleration."
        echo "Please run: conda env create -f voice-agent/environment.yml"
        echo "Or change TTS_TYPE=cartesia in .env to use cloud TTS."
        echo ""
        # cleanup
        bash ./stop_aura.sh
        exit 1
    fi
    (
        cd voice-agent || exit
        eval "$(conda shell.bash hook 2>/dev/null || echo '')"
        conda activate aura
        python agent.py dev
    ) &
    echo $! >> "$PID_FILE"
else
    echo "Detect TTS_TYPE=$TTS_TYPE (Cloud). Using standard venv..."
    (
        cd voice-agent || exit
        source venv/bin/activate
        python agent.py dev
    ) &
    echo $! >> "$PID_FILE"
fi
sleep 2

# 3. AI Service
echo "[3/4] Starting AI Service (port 8000)..."
(
    cd ai-service || exit
    source venv/bin/activate
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) &
echo $! >> "$PID_FILE"
sleep 2

# 4. Dashboard
echo "[4/4] Starting Dashboard (port 5173)..."
(
    cd dashboard || exit
    npm run dev -- --host
) &
echo $! >> "$PID_FILE"
sleep 5

echo ""
echo "=========================================================="
echo "All services running! Press CTRL+C to stop them."
echo "=========================================================="

wait
