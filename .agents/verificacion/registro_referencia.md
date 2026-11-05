# Registro de verificación: ejecución del ORIGINAL desde la copia de referencia

Fecha: 2026-10-30, hora local del equipo acp-client (Windows, PowerShell).
Copia usada como `--raiz`: `.agents\verificacion\referencia_original\`.
Entorno: Python 3.15.2 (`python` del PATH), pandas 3.1.0, numpy 2.5.4, openpyxl 3.1.5, reportlab 5.1.0.

## 1. Controles previos

| Control | Resultado |
|---|---|
| SHA256 de los 8 archivos del manifiesto frente a la copia de referencia | 8 de 8 coinciden |
| `fuentes\` de la referencia frente a `fuentes\` real (ruta, bytes y SHA256; 10 archivos) | Idénticos |
| `resultados\` y `__pycache__` en la referencia antes de correr | No existían |
| `resultados\` real antes de correr | 116 archivos. Snapshot: `logs_referencia\snapshot_resultados_real_ANTES.txt` |

## 2. Corridas del ORIGINAL

Ambas corridas se lanzaron con `Start-Process`, que redirige stdout y stderr a archivos. Los argumentos son los indicados en la instrucción. Se ejecutaron en orden: primero el rango y después el periodo.

### Corrida 1: rango 2026-01 a 2026-08

```
python c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\referencia_original\codigo\indicador_01_tarifas_mcp.py --raiz c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\referencia_original --desde 2026-01 --hasta 2026-08
```

- Código de salida: **0**.
- Tiempo total según el script: 146.97 s.
- stderr: 12 avisos de pandas, `UserWarning: Discarding nonzero nanoseconds in conversion.`, en `indicador_01_tarifas_mcp.py` línea 733. La salida se generó igual.
- stdout: 8 meses calculados. Cada mes imprime una nota de control histórico: 7 operaciones con diferencias internas entre valor, tarifa reportada y cobro.
- Logs: `logs_referencia\ref_run1_rango_stdout.txt`, `ref_run1_rango_stderr.txt`, `ref_run1_rango_exit.txt`.

### Corrida 2: periodo 2025-11

```
python c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\referencia_original\codigo\indicador_01_tarifas_mcp.py --raiz c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\referencia_original --periodo 2025-11
```

- Código de salida: **0**.
- Tiempo total según el script: 23.09 s. stderr vacío.
- Logs: `logs_referencia\ref_run2_periodo_stdout.txt`, `ref_run2_periodo_stderr.txt`, `ref_run2_periodo_exit.txt`.

## 3. Salidas generadas

Están en `c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\referencia_original\resultados\`. Son 9 carpetas. Cada una tiene los mismos 8 archivos: `codigo_utilizado.py`, `dashboard.html`, `detalle_calculo.json`, `metadatos_ejecucion.json`, `nota_auditoria_interna.txt`, `resultado.json`, `resultado_indicador.pdf` y `resultado_indicador.xlsx`.

| Carpeta | Evaluadas | Operaciones | Adiciones | Alertas IND-01 / 02 / 03 / 04 / 05 |
|---|---|---|---|---|
| 2025-11_20261030095728 | 38 | 14 | 24 | 0 / 0 / 0 / 5 / 0 |
| 2026-01_20261030095454 | 47 | 19 | 28 | 0 / 0 / 0 / 8 / 0 |
| 2026-02_20261030095506 | 38 | 10 | 28 | 0 / 0 / 0 / 2 / 0 |
| 2026-03_20261030095521 | 54 | 33 | 21 | 0 / 0 / 0 / 3 / 0 |
| 2026-04_20261030095545 | 44 | 30 | 14 | 0 / 0 / 0 / 1 / 0 |
| 2026-05_20261030095557 | 53 | 33 | 20 | 0 / 0 / 0 / 2 / 0 |
| 2026-06_20261030095611 | 83 | 46 | 37 | 0 / 0 / 1 / 2 / 1 |
| 2026-07_20261030095624 | 57 | 20 | 37 | 0 / 0 / 0 / 9 / 0 |
| 2026-08_20261030095649 | 39 | 25 | 14 | 2 / 0 / 0 / 1 / 0 |

No se generó `Consolidado_alertas_2026.xlsx` en la referencia, porque no se corrió el consolidado anual.

**Advertencia para comparar.** La copia de referencia no trae el historial de `resultados\`, así que la sección comparativa de tres meses de cada corrida solo ve corridas de esta sesión. Por ejemplo, en el `resultado.json` de referencia de 2026-01, el mes 2025-11 queda sin valor (null) en la comparativa de IND-01. La corrida real de 2026-01 muestra 0 en la columna "Tarifas mal aplicadas" para ese mismo mes. La diferencia viene del historial disponible, no del código. Al comparar dashboards, conviene comparar las métricas o reproducir la misma secuencia de corridas.

## 4. Pruebas en la copia de referencia

Se ejecutaron con el directorio de trabajo en la raíz de la referencia. Se usó `PYTHONDONTWRITEBYTECODE=1` para no crear `__pycache__` dentro de la copia, y no quedó ninguno. Las tres pruebas importan `codigo` relativo a su propio archivo, así que probaron el código de la referencia.

| Id | Comando exacto (cwd = `referencia_original`) | Código de salida | Resultado |
|---|---|---|---|
| T1 | `python pruebas\test_reglas_adiciones.py` | 0 | **PASS**. Salida: "Pruebas de frontera superadas: Forward, 0, 30, 31 y fecha anterior." |
| T2 | `python pruebas\test_exportaciones.py` | 1 | **FAIL** (ERROR de unittest). "Ran 1 test", "FAILED (errors=1)". |
| T3 | `python pruebas\test_ejecucion_mensual.py` | 1 | **FAIL**. "Ran 7 tests", "FAILED (errors=1)". 6 de 7 casos pasan. |
| T2v | `python pruebas\test_exportaciones.py -v` | 1 | Mismo resultado, con detalle por caso. |
| T3v | `python pruebas\test_ejecucion_mensual.py -v` | 1 | Mismo resultado, con detalle por caso. |
| D | `python c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\logs_referencia\diagnostico_test_exportaciones.py` (cwd = `logs_referencia`) | 0 | Diagnóstico, no es el resultado oficial. Ver abajo. |

Resultado por caso:

| Archivo | Caso | Resultado real |
|---|---|---|
| test_reglas_adiciones.py | Script con cinco comprobaciones de frontera | PASS |
| test_exportaciones.py | test_excel_y_pdf | FAIL (ERROR) |
| test_ejecucion_mensual.py | test_acumulado_no_incluye_evento_evaluado | PASS |
| test_ejecucion_mensual.py | test_calendario_faltante_y_ultima_corrida | PASS |
| test_ejecucion_mensual.py | test_conversion_decimal_incoherente | FAIL (ERROR) |
| test_ejecucion_mensual.py | test_copia_de_fuentes_usa_ruta_corta_y_categoria | PASS |
| test_ejecucion_mensual.py | test_fuentes_superpuestas_y_conflicto | PASS |
| test_ejecucion_mensual.py | test_mes_invalido | PASS |
| test_ejecucion_mensual.py | test_trazabilidad_cub_convierte_pagina_numerica_a_texto | PASS |

**Fallo esperado, confirmado.** `test_conversion_decimal_incoherente` (línea 68 de `test_ejecucion_mensual.py`) falla con:

```
TypeError: validar_coherencia_base() takes 1 positional argument but 2 were given
```

La firma real, en `codigo\indicador_01_tarifas_mcp.py` línea 1023, es `def validar_coherencia_base(eventos: pd.DataFrame) -> None:`.

**Causa del fallo de test_excel_y_pdf.** Windows impide borrar `resultado_indicador.xlsx` al limpiar la carpeta temporal. El error es `PermissionError: [WinError 32]`, y se lanza al salir del bloque `with tempfile.TemporaryDirectory()`, después de ejecutarse el cuerpo de la prueba. El diagnóstico muestra que las aserciones pasan: con los errores de limpieza ignorados, el caso termina en `ok` (código 0). La causa más probable es que el libro abierto con `load_workbook(excel, read_only=True)` nunca se cierra. No lo comprobé cerrándolo, porque eso exige modificar la prueba. Las ejecuciones fallidas dejaron carpetas temporales en `%TEMP%`, fuera del proyecto y sin borrar. Confirmé dos: `tmpymlf5pjx` y `tmpsluyjvop`.

Logs: `logs_referencia\ref_prueba_test_*`, `ref_verbose_test_*`, `diagnostico_test_exportaciones_*`.

## 5. Verificación posterior a las corridas y pruebas

- SHA256 de los 8 archivos del manifiesto frente a la referencia: 8 de 8 coinciden.
- `codigo_utilizado.py` de las 9 salidas, y el campo `codigo_sha256` de sus `metadatos_ejecucion.json`, coinciden con el manifiesto (`195E128F...`).
- `fuentes\` de la referencia: 10 archivos, sin cambios.
- `resultados\` real: 116 archivos antes y después, 0 diferencias. `Consolidado_alertas_2026.xlsx` sigue igual.
- No hay `__pycache__` en la referencia.

## 6. Lo que no se hizo

- No se corrigió código ni pruebas.
- No se usó `--inicializar`.
- No se corrió el consolidado anual.
- No hubo commit, porque el workspace no es un repositorio git.

## 7. Evidencia

La carpeta `logs_referencia\` contiene stdout, stderr y código de salida de cada comando, los snapshots `snapshot_*` y el driver del diagnóstico `diagnostico_test_exportaciones.py`.
