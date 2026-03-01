@echo off
title AURA Cleanup
echo +--------------------------------------+
echo I        AURA Cleanup Utility          I
echo +--------------------------------------+
echo.

echo Stopping AURA Token Server...
taskkill /F /FI "WINDOWTITLE eq AURA Token Server" /T >nul 2>&1

echo Stopping AURA Voice Agent...
taskkill /F /FI "WINDOWTITLE eq AURA Voice Agent" /T >nul 2>&1

echo Stopping AURA AI Service...
taskkill /F /FI "WINDOWTITLE eq AURA AI Service" /T >nul 2>&1

echo Stopping AURA Dashboard...
taskkill /F /FI "WINDOWTITLE eq AURA Dashboard" /T >nul 2>&1

echo.
echo All AURA services stopped.
timeout /t 2 /nobreak >nul
exit
