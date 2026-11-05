@echo off
setlocal
cd /d "%~dp0"
REM Esta actualizacion ejecuta el codigo Python actualizado, no un EXE anterior.
if "%~1"=="" (
    python "codigo\indicador_01_tarifas_mcp.py" --raiz "."
) else (
    python "codigo\indicador_01_tarifas_mcp.py" --raiz "." --periodo "%~1"
)
echo.
pause
