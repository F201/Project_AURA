#!/usr/bin/env bash

echo "+--------------------------------------+"
echo "|        AURA Cleanup Utility          |"
echo "+--------------------------------------+"
echo ""

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

PID_FILE=".aura_pids"

if [ -f "$PID_FILE" ]; then
    echo "Stopping background processes listed in $PID_FILE..."
    while read -r pid; do
        if [ -n "$pid" ]; then
            if kill -0 "$pid" 2>/dev/null; then
                echo "Killing PID $pid and its descendants..."
                pkill -P "$pid" 2>/dev/null
                kill -9 "$pid" 2>/dev/null
            fi
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
else
    echo "No .aura_pids file found."
fi

# Fallback safely without killing completely unrelated things
echo "Attempting to kill lingering AURA processes..."
pkill -f "token_server.py" 2>/dev/null
pkill -f "agent.py dev" 2>/dev/null
pkill -f "app.main:app" 2>/dev/null
pkill -f "vite.*dashboard" 2>/dev/null

echo ""
echo "All AURA services stopped."
