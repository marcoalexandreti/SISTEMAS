@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0runtime\bin\javaw.exe" goto :incompleto
if not exist "%~dp0PlanilhaPDF.jar" goto :incompleto
if "%~1"=="" (
    "%~dp0runtime\bin\javaw.exe" -Dfile.encoding=UTF-8 -jar "%~dp0PlanilhaPDF.jar"
) else (
    "%~dp0runtime\bin\javaw.exe" -Dfile.encoding=UTF-8 -jar "%~dp0PlanilhaPDF.jar" --abrir "%~f1"
)
exit /b
:incompleto
echo Extraia TODOS os arquivos do ZIP antes de iniciar.
echo Mantenha a pasta runtime junto de PlanilhaPDF.jar.
pause
exit /b 1
