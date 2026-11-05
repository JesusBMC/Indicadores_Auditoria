# Corrección 1.6.1

Esta corrección resuelve el error:

```text
TypeError: Invalid value '43' for dtype 'str'
```

El error se presentó cuando la versión de pandas instalada en Anaconda intentó
guardar el número de página del CUB dentro de la trazabilidad del cálculo. No
afecta las fuentes ni los valores de tarifas.

## Reemplazo

1. Extraiga este ZIP dentro de la carpeta principal `Indicador_01_Tarifas_MCP`.
2. Acepte reemplazar únicamente:

```text
codigo\indicador_01_tarifas_mcp.py
```

No requiere modificar `fuentes`, `resultados`, las bases ni ejecutar de nuevo
`pip install -r requirements.txt`.

## Ejecución

Desde Anaconda Prompt, ubicado en la carpeta principal del indicador, ejecute:

```bat
ejecutar_indicador_01.bat 2026-08
```

La nueva ejecución debe generar `dashboard.html`, `resultado_indicador.pdf` y
`resultado_indicador.xlsx` en una nueva carpeta dentro de `resultados`.
