@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 run_tests.py
  if errorlevel 1 goto :fail
  py -3 tests\regression_matrix.py
  if errorlevel 1 goto :fail
) else (
  python run_tests.py
  if errorlevel 1 goto :fail
  python tests\regression_matrix.py
  if errorlevel 1 goto :fail
)
echo.
echo MILESTONE 1: ALLE PRUEFUNGEN BESTANDEN
goto :end
:fail
echo.
echo MILESTONE 1: FEHLER GEFUNDEN
:end
pause
