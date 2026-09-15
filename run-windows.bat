@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw nokia_video_converter.py
) else (
    python nokia_video_converter.py
    if errorlevel 1 pause
)
