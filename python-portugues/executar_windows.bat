@echo off
setlocal
set "PT_INTERPRETADOR=%~dp0Python-3.14.10\PCbuild\amd64\python.exe"
if not exist "%PT_INTERPRETADOR%" (
    echo Compile primeiro usando compilar_windows.bat.
    pause
    exit /b 1
)
if "%~1"=="" (
    "%PT_INTERPRETADOR%" "%~dp0exemplos\inicio.ptpy"
) else (
    "%PT_INTERPRETADOR%" "%~f1"
)
if errorlevel 1 pause
