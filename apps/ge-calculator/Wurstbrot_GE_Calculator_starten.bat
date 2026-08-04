@echo off
setlocal
cd /d "%~dp0\..\.."
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 apps\ge-calculator\ge_calculator_gui.py
) else (
    python apps\ge-calculator\ge_calculator_gui.py
)
if errorlevel 1 pause
