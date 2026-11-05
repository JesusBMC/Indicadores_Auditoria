# Actualización 1.2.0 — Indicador 01 · Tarifas MCP

## Cambios incorporados

El dashboard ahora tiene cinco vistas independientes, disponibles mediante los botones `IND-01` a `IND-05`:

1. Tarifas mal aplicadas — MCP Registro de operación — punta compradora.
2. Tarifas mal aplicadas — MCP Registro de operación — punta vendedora.
3. Tarifas mal aplicadas — MCP Servicio de compensación y liquidación — ambas puntas.
4. Tarifas mal aplicadas — MCP Registro de adición — punta compradora.
5. Tarifas mal aplicadas — MCP Registro de adición — punta vendedora.

La tercera vista utiliza los valores sin IVA cargados para compensación y liquidación y las tarifas CUB MCP: 0,185 % para Disponible y 0,210 % para Forward, para cada punta.

En cada vista se presenta la población, las tarifas mal aplicadas, los registros no evaluables y el detalle de cálculo. Al imprimir el dashboard en PDF, cada indicador se presenta en una página independiente.

## Actualizar el programa

1. Copie el ZIP en la carpeta principal `Indicador_01_Tarifas_MCP`.
2. Extraiga el ZIP seleccionando esa misma carpeta como destino.
3. Acepte reemplazar los archivos cuando Windows lo solicite.
4. Ejecute `ejecutar_indicador_01.bat`.

La actualización reemplaza solamente `codigo\indicador_01_tarifas_mcp.py` y `README.md`. No modifica las fuentes ni los resultados existentes.

La nueva corrida crea una carpeta adicional en `resultados`; los resultados anteriores se conservan sin cambios.
