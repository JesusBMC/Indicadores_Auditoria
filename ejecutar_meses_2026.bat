@echo off
setlocal
cd /d "%~dp0"
REM Sin argumentos calcula enero-agosto. Puede indicar otro rango AAAA-MM AAAA-MM.
set "periodo_mcp_desde=2026-01"
set "periodo_mcp_hasta=2026-08"
if not "%~1"=="" set "periodo_mcp_desde=%~1"
if not "%~2"=="" set "periodo_mcp_hasta=%~2"
python "codigo\indicador_01_tarifas_mcp.py" --raiz "." --desde "%periodo_mcp_desde%" --hasta "%periodo_mcp_hasta%"
echo.
pause
