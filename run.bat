@echo off
echo Starting DM SQL Optimizer...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Application exited with error code %errorlevel%.
    pause
)
