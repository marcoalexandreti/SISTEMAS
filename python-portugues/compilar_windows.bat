@echo off
setlocal
cd /d "%~dp0"
py -3 preparar.py
if errorlevel 1 goto :erro
pushd Python-3.14.10
call PCbuild\build.bat -p x64
if errorlevel 1 (
    popd
    goto :erro
)
popd
echo.
echo Compilacao concluida. Executando o exemplo:
Python-3.14.10\PCbuild\amd64\python.exe exemplos\inicio.ptpy
if errorlevel 1 goto :erro
pause
exit /b 0
:erro
echo.
echo Falha. Consulte os requisitos no LEIA-ME.md e as mensagens acima.
pause
exit /b 1
