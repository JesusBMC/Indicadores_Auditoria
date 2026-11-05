# Indicador 01 · Tarifas MCP: informe de situación

## Resumen

El proyecto es una herramienta en Python (pandas) que valida cada mes si las tarifas cobradas por registro MCP (operaciones y adiciones) y por compensación y liquidación (CyL) coinciden con las tarifas del PT CUB. Las diferencias mayores a COP 1 se marcan como alertas, y cada corrida guarda su evidencia en `resultados\`.

Está construido el flujo completo: carga de fuentes, clasificación de adiciones, acumulados por tramos, cinco indicadores, dashboard HTML, Excel, PDF, JSON de trazabilidad, consolidado anual y ocho corridas de enero a agosto de 2026 con la versión 1.7.0.

Pendientes principales: la vista comparativa de tres meses no aparece en el dashboard 1.7.0, la copia de fuentes que describe la documentación no se ejecuta, el README está desactualizado, y la base de operaciones de enero a agosto de 2026 cambió después de las corridas (su hash ya no coincide con el registrado).

Alcance: lectura de código, README, instrucciones, `.bat`, JSON y HTML de `resultados`. No ejecuté scripts ni pruebas, no abrí los `.xlsx` y no modifiqué el repositorio. Los hashes se calcularon con `Get-FileHash`.

## 1. Propósito

- **Qué mide:** si el cobro de las tarifas de registro MCP (punta compradora y vendedora, en operaciones y adiciones) y de compensación y liquidación (ambas puntas) coincide con la tarifa esperada del CUB. Fuente: `codigo\indicador_01_tarifas_mcp.py` (docstring; `obtener_vistas`, L713).
- **Ciclo:** mensual, por período `AAAA-MM`, con acumulados anuales de enero a diciembre (`recalcular`, L384). El README no declara periodicidad; lo infiero de los `.bat` y de `ejecutar_meses_2026.bat`.
- **Destinatarios:** las notas técnicas son para Auditoría Interna y no van al HTML que se comparte con el auditado (comentario en `html_reporte_v2`, L924 a L927). El consolidado está dirigido a la Administración (docstring de `codigo\generar_consolidado_alertas_anual.py`).
- **Estado de validación:** todas las salidas indican "Información en proceso de validación" (`html_reporte_v2`, `exportar_excel`, `exportar_pdf`).

## 2. Entradas

Todas son archivos `.xlsx` bajo `fuentes\` (README, "Fuentes que se cargan"; `cargar_datos`, L1030).

- **`fuentes\operaciones\`:** una o varias bases. Columnas obligatorias (`leer_operaciones`, L139): NumeroOperacion, negocio, FechaOperacion, FechaEntregaFin, MandanteCompra, ValorNegocio, ValorRegistroC, ValorRegistroV. Opcionales: PorcRegistroC/V y ValorCamaraC/V (cobro CyL).
- **`fuentes\adiciones\`:** `leer_adiciones` (L186). Obligatorias: Operacion, ValorAdicion, NoAdicion, RegistroCompra, RegistroVenta, FechaSolicitud, FechaEntrega. Opcionales: CylCompra/CylVenta.
- **`fuentes\parametros\`:** exactamente un PT CUB en `.xlsx`, con hoja "Inventario" o "Detalle tarifas" (`hoja_y_encabezado_tarifas`, L227; `extraer_tarifas`, L268). Solo usa filas del mercado MCP.
- **`fuentes\parametros\configuracion_ejecucion.json`:** `periodo_evaluado` (hoy `2025-11`) y `tolerancia_cop` (hoy `1`). `cargar_configuracion`, L955.
- Los `.xls` y `.xlsb` se ignoran y se registran como aviso (`cargar_datos`, `ejecutar`).

## 3. Proceso

Reglas en el orden en que se aplican:

1. **Universo MCP:** negocio `DISMCP` (Disponible) o `FRWMCP` (Forward), según `MCP_CODIGOS` (L30). Quedan fuera `DISPSG`, `FWRDSG`, `FWRD` (`EXCLUIDOS`, L31) y cualquier otro negocio.
2. **Duplicados:** las filas idénticas entre archivos se eliminan. Si una operación aparece con datos distintos, la corrida se detiene (`depurar_repetidos`, L979).
3. **Clasificación de adiciones:** se hace con la operación original, no con la base de adiciones (`clasificar_adiciones`, L334). Original Forward da Forward. Original Disponible con entrega hasta 30 días después da Disponible; con más de 30 días da Forward. Entrega anterior, original ausente o duplicada da "no evaluable".
4. **Tarifa de registro del comprador:** depende del acumulado previo del comprador en el año, por naturaleza. Tramos: hasta 200.000 millones de COP, de 200.000 a 500.000 millones, de 500.000 millones a 1 billón, y más de 1 billón. Los límites están escritos en el código (`extraer_tarifas`, L292 a L303), no se leen del PT.
5. **Tarifa del vendedor y de CyL:** una tarifa por naturaleza, sin tramos. `tarifa_para` (L367) devuelve la primera fila que coincide. Las tasas CyL (0,185 % Disponible y 0,210 % Forward) se leen del PT; no aparecen escritas en el código.
6. **Acumulado:** suma el `valor_base` de operaciones y adiciones del mismo comprador, año y naturaleza, en orden de fecha. Usa el acumulado previo al evento (`recalcular`; prueba `test_acumulado_no_incluye_evento_evaluado`).
7. **Resultado:** registro esperado = valor base × tarifa esperada. Tarifa aplicada = registro cobrado / valor base (`tarifa_aplicada`, L117). Hay alerta si la diferencia absoluta supera la tolerancia. Es "no evaluable" si falta un dato o la adición no está clasificada.
8. **Control bloqueante:** en las operaciones del mes, si valor base × porcentaje reportado no concilia con el cobro (tolerancia: el mayor entre COP 100 y 0,001 % del valor), la corrida se detiene (`validar_coherencia_base`, L1023). En meses anteriores solo genera un aviso.

Una operación entra al mes por FechaOperacion y una adición por FechaSolicitud. Los acumulados usan todos los eventos hasta el fin del mes evaluado.

## 4. Salidas

Cada corrida crea `resultados\AAAA-MM_AAAAMMDDHHMMSS\` (`crear_carpeta_resultado`, L1060; `ejecutar`, L1115). Nunca sobrescribe; si la carpeta existe, agrega un sufijo `_2`.

- `dashboard.html`: pestañas IND-01 a IND-05, indicadores, detalle de alertas, no evaluables y cálculo, y mini gráficas de tres meses por indicador.
- `resultado_indicador.xlsx`: hojas Resumen e IND_01 a IND_05 (`exportar_excel`, L771).
- `resultado_indicador.pdf`: A3 horizontal, una sección por indicador (`exportar_pdf`, L842).
- `resultado.json`: métricas normalizadas por indicador y serie de tres meses.
- `metadatos_ejecucion.json`: versión, SHA-256 y tamaño de cada fuente, configuración efectiva, control de carga, notas de auditoría y tiempo.
- `detalle_calculo.json`, `codigo_utilizado.py` y, si hay avisos, `nota_auditoria_interna.txt`.
- **Consolidado anual:** `resultados\Consolidado_alertas_2026.xlsx`, generado por `codigo\generar_consolidado_alertas_anual.py`. Tiene las hojas "Resumen mensual", "Detalle de alertas" y "Corridas incluidas". Toma la última carpeta de cada mes por fecha de modificación. No abrí el archivo.

## 5. Estado actual

**Versión vigente: 1.7.0** (`VERSION`, L29; `version_codigo` de las corridas 2026; `codigo_utilizado.py`).

Cambios según las instrucciones y su estado en el código de 1.7.0:

| Versión | Cambio documentado | Estado en 1.7.0 |
|---|---|---|
| 1.2.0 | Cinco vistas IND-01 a IND-05 | Presente |
| 1.3.0 | Comparativo de tres meses en tabla | Ausente (pendiente 2) |
| 1.4.0 | Dos gráficas de barras agrupadas en el comparativo | Ausente (pendiente 2) |
| 1.6.1 | Corrección de tipo en la página CUB | Presente (`texto_trazabilidad`, L112) |
| 1.6.2 | Copia de fuentes con nombres cortos | Función presente, sin uso (pendiente 3) |

No hay instrucciones para 1.5.x, 1.6.0 ni 1.7.0. Las carpetas de `resultados` van de 1.0.1 a 1.7.0. Las cinco carpetas de 2025 (creadas el 23/09/2026) parecen pruebas de desarrollo; las ocho de 2026 (25/10/2026) son las corridas de enero a agosto.

Alertas por indicador en cada corrida de 2026 (`indicators.IND-0X.alerts` de `resultado.json`). Ninguna corrida tiene registros no evaluables.

| Mes 2026 | IND-01 | IND-02 | IND-03 | IND-04 | IND-05 |
|---|---|---|---|---|---|
| Enero | 0 | 0 | 0 | 8 | 0 |
| Febrero | 0 | 0 | 0 | 2 | 0 |
| Marzo | 0 | 0 | 0 | 3 | 0 |
| Abril | 0 | 0 | 0 | 1 | 0 |
| Mayo | 0 | 0 | 0 | 2 | 0 |
| Junio | 0 | 0 | 1 | 2 | 1 |
| Julio | 0 | 0 | 0 | 9 | 0 |
| Agosto | 2 | 0 | 0 | 1 | 0 |

En agosto, la población fue de 25 operaciones y 14 adiciones, con 3 alertas. La diferencia neta de IND-01 fue de COP 2.426.530 y la de IND-04 de −COP 83.027. Según la convención del consolidado (cobro aplicado menos cobro esperado), IND-04 tuvo diferencia neta negativa en 7 de 8 meses.

**Pruebas (no ejecutadas):**
- `pruebas\test_reglas_adiciones.py`: script documentado en el README. Prueba Forward, los límites de 0, 30 y 31 días y la fecha anterior.
- `pruebas\test_ejecucion_mensual.py`: 7 casos. Calendario y última corrida, duplicados, acumulado con umbral, mes inválido, conversión decimal, trazabilidad CUB y copia de fuentes.
- `pruebas\test_exportaciones.py`: 1 caso. Hojas del Excel y cabecera del PDF.

No hay pruebas para la lectura del PT real, el tramo de 500.000 millones a 1 billón, la tarifa del vendedor, el cálculo de alertas, el flujo completo de `ejecutar()`, la línea de comandos ni el consolidado.

## 6. Pendientes y observaciones

Etiquetas: [C] confirmado en código o archivos; [I] inferencia.

1. **Fuente modificada después de las corridas [C].** `fuentes\operaciones\Operaciones MCP enero-agosto 2026.xlsx` mide 101.662 bytes y su SHA-256 es `7f07e9…`. Las ocho corridas 2026 registraron `b37b6c…` con 101.407 bytes (`metadatos_ejecucion.json`). Las demás nueve fuentes y el código sí coinciden. El cambio es posterior a la corrida de 2026-08 (19:24 del 25/10/2026). No hay forma de saber desde el repositorio quién lo cambió ni por qué.
2. **Comparativo de tres meses ausente [C].** En `html_reporte_v2`, la variable `comparativo` queda vacía (L917). `panel_comparativo_tres_meses` (L699) nunca se llama. Los dashboards 1.3.0 y 1.4.0 de 2025 sí tienen la sección con gráficas. Los de 2026 solo muestran mini gráficas en cada tarjeta. No hay comentario que indique si la eliminación fue intencional.
3. **Copia de fuentes no ejecutada [C].** `copiar_fuentes_resultado` (L1071) solo la llama `pruebas\test_ejecucion_mensual.py` (L85). Un comentario en `ejecutar` indica que se decidió no copiar. Sin embargo, el README (sección de resultados) y la instrucción 1.6.2 la describen, y el encabezado del dashboard sigue diciendo "copia de fuentes".
4. **README desactualizado [C].** Dice que no genera resultados en Excel, pero produce `.xlsx` y `.pdf`. Describe una carpeta `fuentes_utilizadas` que 1.7.0 no crea. Dice que `ejecutar_indicador_01.bat` abre el ejecutable si existe, pero el `.bat` siempre llama a Python y no existe la carpeta `ejecutable\`. No menciona el consolidado, las pruebas `unittest` ni la versión. Sus ejemplos de nombres (`operaciones_2026_enero_julio.xlsx`, `operaciones_2023.xlsx`) no coinciden con los archivos reales.
5. **Prueba que fallaría [C, por lectura].** `test_ejecucion_mensual.py::test_conversion_decimal_incoherente` llama `validar_coherencia_base(fila, 1)`, pero la función (L1023) solo acepta un argumento. No la ejecuté.
6. **Código sin uso o incompleto [C].** `html_reporte` (L474) es una versión anterior del dashboard. Tampoco se usan `panel_comparativo_tres_meses`, `copiar_fuentes_resultado` (solo pruebas), las columnas `iva_registro_*` (L202 a L203) ni `fuera_mcp`, que se calcula pero `ejecutar` no usa. Además, `resultado.json` escribe `"warnings": []` fijo, así que los avisos solo llegan a `metadatos_ejecucion.json` y a `nota_auditoria_interna.txt`.
7. **Conteo mal nombrado [C].** `operaciones_fuera_mcp` (394 en 2026-08) también incluye operaciones con inconsistencias del origen, porque `preparar_originales` (L315) devuelve ambas listas juntas. La rama "información inconsistente" nunca se activa, porque `depurar_repetidos` ya detiene la corrida [I, por lectura del flujo].
8. **Cobertura histórica sin control [C]; efecto [I].** El acumulado anual exige que estén todos los meses previos. Solo hay aviso cuando una adición no tiene original (L1143). Si faltan meses, las tarifas esperadas de los meses siguientes serían incorrectas sin alerta.
9. **Inconsistencias históricas sin bloqueo [C].** La corrida 2026-08 avisa que 7 operaciones históricas tienen diferencias internas entre valor, tarifa reportada y cobro. Pueden alterar los acumulados. Su efecto no se cuantificó (`nota_auditoria_interna.txt`).
10. **Valores fijos [C].** Umbrales de tramos (L296 a L302), códigos `DISMCP` y `FRWMCP` (L30), exclusiones (L31), periodo por defecto `2025-11` en `inicializar` y año 2026 por defecto en el consolidado. No hay rutas absolutas.
11. **Dos criterios de "última corrida" [C].** El dashboard usa `generated_at` (`cargar_comparativo_tres_meses`, L551). El consolidado usa la fecha de modificación de la carpeta (`obtener_corridas_resultados`). Pueden elegir corridas distintas.
12. **Alertas contadas dos veces en el consolidado [C].** "Alertas (registros)" suma las alertas de los cinco indicadores. Una operación con alerta en compra y en venta cuenta dos veces. El script no tiene `.bat` ni aparece en el README.
13. **Errores no controlados [C].** `main()` (L1210) solo captura `OSError`, `ValueError`, `KeyError` e `ImportError`. Un `TypeError`, como el de la versión 1.6.1, muestra un traceback. En modo rango, el error de un mes corta los meses siguientes. Si una exportación falla, la carpeta queda sin `resultado.json`.
14. **Lectura numérica por heurística [C].** `numero()` (L49) interpreta "1.234" como 1,234. `porcentaje()` (L64) trata 0,3 como 30 % cuando el texto no tiene el símbolo %. El control del punto 7 de Proceso solo protege las operaciones, no las adiciones ni el PT.
15. **Ejecutable [I].** `construir_ejecutable_windows.bat` no instala `reportlab`, aunque `requirements.txt` la pide. En un ejecutable de PyInstaller, `Path(__file__)` (L1154 y L1163) puede no existir en disco, y la copia del código y el hash fallarían. No lo probé.
16. **Versión de pandas sin fijar [C].** `requirements.txt` pide `pandas>=2.0`. El error de la versión 1.6.1 depende de la versión instalada, y las corridas no registran cuál se usó.
17. **Valores sin IVA [no determinado].** El README dice que CyL usa valores sin IVA. El código toma `ValorCamaraC/V` y `CylCompra/V` tal cual y no resta IVA. Sin abrir los Excel no puedo confirmar el contenido.

## 7. Cómo ejecutarlo

Desde Anaconda Prompt, en la carpeta principal:

1. `pip install -r requirements.txt` (pandas, openpyxl y reportlab). El README no lo indica; la instrucción 1.6.1 sí.
2. `python codigo\indicador_01_tarifas_mcp.py --inicializar` (una sola vez).
3. Copiar las bases a `fuentes\operaciones` y `fuentes\adiciones`, y dejar un único PT en `fuentes\parametros`.
4. `python pruebas\test_reglas_adiciones.py`.
5. Calcular un mes: `ejecutar_indicador_01.bat 2026-08`. Sin argumento usa `periodo_evaluado` (hoy 2025-11). Para varios meses: `ejecutar_meses_2026.bat 2026-01 2026-08`; estos son también los valores por defecto.
6. Consolidado anual: `python codigo\generar_consolidado_alertas_anual.py --anio 2026`.
7. Pruebas `unittest`: `python pruebas\test_ejecucion_mensual.py` y `python pruebas\test_exportaciones.py`. Según la lectura, el caso de conversión decimal fallaría (pendiente 5).
8. Ejecutable: `construir_ejecutable_windows.bat` genera `ejecutable\Indicador_01_Tarifas_MCP.exe`, pero los `.bat` no lo usan.

## Conclusiones y recomendaciones

1. **Antes de usar cifras de 2026, aclarar el cambio del archivo de enero a agosto.** Si el original es el registrado, restaurarlo. Si el cambio es válido, volver a correr 2026-01 a 2026-08 y documentarlo.
2. **Decidir si el comparativo y la copia de fuentes son intencionales.** Si lo son, actualizar README e instrucciones. Si no, restaurar la llamada a `panel_comparativo_tres_meses` en `html_reporte_v2` (L917) y llamar `copiar_fuentes_resultado` desde `ejecutar`.
3. **Actualizar la documentación.** Escribir la instrucción de 1.7.0 y corregir el README (Excel y PDF, consolidado, ejecutable, pruebas y versión).
4. **Corregir la prueba rota y cubrir los vacíos.** Añadir pruebas con el PT real, los tramos, la cobertura mensual y el flujo completo de `ejecutar()`.
5. **Controlar la cobertura de meses previos y el PT.** El programa debería detenerse si el PT no tiene los tramos esperados o si faltan meses para el acumulado.
6. **Unificar el criterio de "última corrida"** y aclarar si el consolidado cuenta alertas por registro o por indicador.
7. **Fijar la versión de pandas** y registrarla en `metadatos_ejecucion.json`.

Preguntas abiertas para la persona responsable: ¿el archivo de enero a agosto se reemplazó a propósito?, ¿la vista comparativa se quitó a propósito en 1.7.0?, ¿las columnas `ValorCamaraC/V` y `CylCompra/V` vienen sin IVA?
