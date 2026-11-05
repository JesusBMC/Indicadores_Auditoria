# Indicador 01 – Tarifas de registro MCP

Esta aplicación valida las tarifas MCP de registro y de compensación y
liquidación, usando las bases de operaciones, la base de adiciones y el PT de
entendimiento de tarifas CUB. Produce un dashboard HTML y conserva la evidencia
de cada ejecución. No genera resultados en Excel.

## Estructura

Ejecute una vez el comando de inicialización. La aplicación creará:

```text
fuentes/
  operaciones/       Bases anuales y mensuales de operaciones
  adiciones/         Base de adiciones
  parametros/        PT CUB y configuración de la corrida
resultados/          Una subcarpeta por cada ejecución
```

## Fuentes que se cargan

| Carpeta | Archivo | Uso |
|---|---|---|
| `fuentes/operaciones` | Uno o varios XLSX | Operaciones originales. Se buscan en todos los archivos cargados. |
| `fuentes/adiciones` | Uno o varios XLSX | Adiciones por operación original. |
| `fuentes/parametros` | PT de inventario CUB en XLSX | Fuente de las tarifas de registro MCP. |
| `fuentes/parametros` | `configuracion_ejecucion.json` | Período y tolerancia de la corrida. |

La primera carga de un año puede ser una base consolidada. Por ejemplo,
`operaciones_2026_enero_julio.xlsx`. Después se agregan solo los archivos de
cada mes y no se eliminan los anteriores.

Las bases históricas, por ejemplo `operaciones_2023.xlsx` y
`operaciones_2024.xlsx`, se copian también en `fuentes/operaciones`. En la
siguiente corrida se incorporan automáticamente a la búsqueda de la operación
original de cada adición; no se requiere cambiar la configuración ni cargar de
nuevo la base de adiciones.

## Regla de clasificación de adiciones

La aplicación no toma la naturaleza desde la base de adiciones. Busca la
operación original y aplica estas reglas:

1. Original Forward: la adición es Forward.
2. Original Disponible y entrega de adición igual o hasta 30 días posterior:
   la adición es Disponible.
3. Original Disponible y entrega de adición más de 30 días posterior:
   la adición es Forward.
4. Entrega de adición anterior, operación original no encontrada, duplicada o
   inconsistente: la adición queda como no evaluable, sin clasificación asumida.

El archivo `pruebas/test_reglas_adiciones.py` valida los límites 0, 30 y 31
días antes de realizar una corrida.

## Resultados y trazabilidad

Cada corrida crea una carpeta de resultados con el formato
`AAAA-MM_fecha_hora`. Dentro se guardan:

- `dashboard.html`: indicadores, conclusión, alertas y detalle de cálculo.
- El dashboard presenta por separado las operaciones y las adiciones. Para
  cada punta muestra la tarifa efectivamente aplicada (registro cobrado / valor
  base), la tarifa esperada, los valores y la diferencia.
- El dashboard contiene cinco vistas independientes: registro de operaciones
  para punta compradora, registro de operaciones para punta vendedora,
  compensación y liquidación para ambas puntas, registro de adiciones para
  punta compradora y registro de adiciones para punta vendedora.
- El dashboard incorpora una vista inicial de comparación de los últimos tres
  meses. Para cada indicador presenta población, tarifas mal aplicadas,
  registros no evaluables, diferencia neta de alertas y la tendencia frente al
  período anterior. Se toma la última corrida disponible por mes.
- La vista comparativa incluye gráficas de barras por indicador para las
  tarifas mal aplicadas y la diferencia neta de las alertas de los tres meses.
- La validación de compensación y liquidación usa los valores sin IVA de cada
  punta y las tarifas MCP de 0,185 % para Disponible y 0,210 % para Forward.
- `resultado.json`: resumen normalizado para el dashboard consolidado futuro.
- `metadatos_ejecucion.json`: versión del código, tiempo total de ejecución y
  huella SHA-256 de fuentes.
- `fuentes_utilizadas`: copia de los archivos utilizados en la corrida.

Las fuentes originales no se modifican ni se sobreescriben los resultados
anteriores.

## Ejecutar en Anaconda Prompt

Inicializar, una sola vez:

```bat
python codigo\indicador_01_tarifas_mcp.py --inicializar
```

Validar reglas de clasificación:

```bat
python pruebas\test_reglas_adiciones.py
```

Ejecutar la corrida:

```bat
ejecutar_indicador_01.bat
```

## Crear ejecutable Windows

Después de validar el resultado de prueba, ejecute una única vez:

```bat
construir_ejecutable_windows.bat
```

Luego podrá usar `ejecutar_indicador_01.bat`; este abrirá el ejecutable si ya
existe y conservará la misma estructura de fuentes y resultados.
