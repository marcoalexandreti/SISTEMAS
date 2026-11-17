@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\bin\javaw.exe" -Dfile.encoding=UTF-8 -jar "%~dp0PlanilhaPDF.jar" --abrir "%~dp0exemplos\exemplo.csv"
