# Corrección 1.6.2 - Rutas de Windows

Esta corrección resuelve el mensaje:

```text
ERROR: [WinError 3] El sistema no puede encontrar la ruta especificada
```

El cálculo terminaba correctamente, pero Windows no podía copiar algunas fuentes
a la carpeta de resultados porque la ruta completa superaba su límite de
longitud. La actualización acorta los nombres internos de la evidencia y
mantiene la trazabilidad del origen de cada archivo.

## Reemplazo

1. Extraiga este ZIP dentro de `Indicador_01_Tarifas_MCP`.
2. Acepte reemplazar:

```text
codigo\indicador_01_tarifas_mcp.py
```

No cambie las bases, las carpetas `fuentes` o los resultados previos. Tampoco
es necesario instalar nuevamente las dependencias.

## Ejecución

Desde Anaconda Prompt, ubicado en la carpeta principal del indicador, ejecute:

```bat
ejecutar_indicador_01.bat 2026-08
```

La nueva salida conservará las copias de las fuentes en una ruta corta:

```text
resultados\2026-08_fecha\fuentes\operaciones__NombreArchivo.xlsx
```

También generará `dashboard.html`, `resultado_indicador.pdf` y
`resultado_indicador.xlsx`.
