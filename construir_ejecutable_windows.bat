@echo off
setlocal
cd /d "%~dp0"

python -m pip install pyinstaller pandas openpyxl
python -m PyInstaller --noconfirm --onefile --name Indicador_01_Tarifas_MCP --distpath ejecutable --workpath temporal_build --specpath temporal_build "codigo\indicador_01_tarifas_mcp.py"

echo.
echo Si no aparecieron errores, el ejecutable esta en la carpeta ejecutable.
pause
