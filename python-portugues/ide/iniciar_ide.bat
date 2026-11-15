@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto :python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto :requisitos
py -3 "%~dp0ide.py"
if errorlevel 1 pause
exit /b
:python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto :requisitos
python "%~dp0ide.py"
if errorlevel 1 pause
exit /b
:requisitos
echo.
echo Instale Python 3.12 ou superior, incluindo Tcl/Tk.
echo Download oficial: https://www.python.org/downloads/windows/
echo Consulte o README.md desta pasta.
pause
exit /b 1
