\
@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 wurstbrot_converter.py --gui
    goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python wurstbrot_converter.py --gui
    goto :end
)

echo Python 3 wurde nicht gefunden.
echo Bitte Python installieren und "Add Python to PATH" aktivieren.
pause

:end
