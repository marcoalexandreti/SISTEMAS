@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\bin\java.exe" -Dfile.encoding=UTF-8 -jar "%~dp0PlanilhaPDF.jar"
if errorlevel 1 pause
