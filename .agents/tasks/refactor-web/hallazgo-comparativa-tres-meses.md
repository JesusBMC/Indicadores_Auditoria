# Hallazgo: comparativa de tres meses en el Indicador 01 (código 1.7.0)

Fecha de la investigación: 30/10/2026.
Alcance: solo lectura del proyecto. Este archivo es el único cambio. El prototipo se hizo en `.agents\verificacion\hallazgo_tres_meses\` y se borró al terminar.

Convención: **[COMPROBADO]** significa leído en código o archivos, encontrado con búsquedas, o reproducido en el prototipo. **[SUPUESTO]** significa inferencia o dato que no pude verificar.

## Respuesta corta

- **La parte visual está desconectada.** [COMPROBADO] Ninguna línea del proyecto llama a `panel_comparativo_tres_meses`. En `html_reporte_v2`, la variable `comparativo` se asigna con `""` (línea 917) y la barra de pestañas solo tiene IND-01 a IND-05 (línea 912).
- **Los datos no están desconectados.** [COMPROBADO] La serie de tres meses se calcula en cada corrida (línea 913) y alimenta las mini gráficas de las tarjetas.
- **No depende de una condición.** [COMPROBADO] No existe bandera, parámetro ni rama que active el panel. Está apagado por código.
- **Ventanas completas solo desde marzo de 2026.** [COMPROBADO] Las ventanas de marzo a agosto de 2026 tienen corridas para sus tres meses. Faltan meses en las ventanas de noviembre de 2025 (septiembre y octubre) y de enero y febrero de 2026 (diciembre de 2025).
- **Cambio mínimo.** [COMPROBADO] Se reemplazan 8 líneas por 11, en 5 bloques (sección 5). El cambio restaura la llamada, agrega la pestaña "Comparativo 3 meses" como vista inicial y evita mostrar ceros en meses sin datos. En una copia, los resultados de cálculo son idénticos al código actual en 2025-11 y 2026-08.

## 1. Función, líneas y llamadas

Archivo: `codigo\indicador_01_tarifas_mcp.py`. [COMPROBADO]

| Función | Línea | Qué dibuja | Quién la llama |
|---|---|---|---|
| `html_reporte_v2` | 887 | Dashboard completo | `ejecutar`, línea 1156 |
| `cargar_comparativo_tres_meses` | 551 | Serie de tres meses por indicador | `html_reporte_v2`, línea 913 |
| `vista_indicador` | 528 | Tarjeta de indicador con dos mini gráficas | `html_reporte_v2`, línea 915 |
| `mini_grafica` | 611 | Tres barras por mini gráfica | `vista_indicador`, líneas 539 y 540 |
| `grafico_comparativo` | 652 | Gráfica agrupada SVG | `panel_comparativo_tres_meses`, líneas 708 y 709 |
| `panel_comparativo_tres_meses` | 699 | Sección con 5 tablas y 2 gráficas | **Ninguna** |

- La línea 917 asigna `comparativo = ""`. La línea 922 inserta esa variable en el documento. [COMPROBADO]
- Los botones de pestaña se crean solo para IND-01 a IND-05 (línea 912). [COMPROBADO]
- `panel_comparativo_tres_meses` aparece en la definición de `codigo\`, en las copias del código guardadas dentro de `resultados\` y `.agents\verificacion\`, y en ningún otro punto. No aparece en `pruebas\`, en los `.bat` ni en `codigo\generar_consolidado_alertas_anual.py`. [COMPROBADO]
- No hay comentario junto a la línea 917. `configuracion_ejecucion.json` solo tiene `periodo_evaluado` y `tolerancia_cop`. [COMPROBADO]
- El repositorio no tiene carpeta `.git`, así que no hay historial para saber cuándo se quitó la llamada. [COMPROBADO]
- [SUPUESTO] La asignación explícita a cadena vacía y la falta de botón sugieren que el panel se retiró a propósito, en favor de las mini gráficas de cada tarjeta. Las pruebas cubren `cargar_comparativo_tres_meses` y `mini_grafica` (`pruebas\test_ejecucion_mensual.py`, líneas 27 y 32), pero no el panel.

## 2. Qué mostró cada versión

Revisé los HTML por búsquedas de estructura y texto. No los abrí en un navegador. [COMPROBADO]

| Versión | Carpeta de `resultados` | Sección comparativa | Pestaña inicial | Gráficas SVG del comparativo | Mini gráficas en tarjetas |
|---|---|---|---|---|---|
| 1.0.1 | `2025-11_20260923_150131` | No | No hay pestañas | 0 | No |
| 1.2.0 | `2025-11_20260923_153722` y `_155725` | No | IND-01 | 0 | No |
| 1.3.0 | `2025-11_20260923_161337` | Sí, 5 tablas | "Comparativo 3 meses" | 0 | No |
| 1.4.0 | `2025-11_20260923_161814` | Sí, 5 tablas | "Comparativo 3 meses" | 2 | No |
| 1.5.x y 1.6.0 | Sin corridas | No hay datos | No hay datos | No hay datos | No hay datos |
| 1.7.0 | `2025-11_20261029153022` y nueve de 2026 | No | IND-01 | 0 | Sí, 10 por dashboard |

[COMPROBADO] Los números de versión vienen de `metadatos_ejecucion.json` y `resultado.json` de cada carpeta.

- En 1.3.0 y 1.4.0, cada tabla tiene las columnas Período, Población, Tarifas mal aplicadas, No evaluables, Diferencia neta de alertas y Tendencia de alertas. Cada tabla tiene una fila por mes con datos.
- En 1.4.0 se agregan dos gráficas de barras agrupadas, "Tarifas mal aplicadas por indicador" y "Diferencia neta de alertas por indicador".
- Las instrucciones `INSTRUCCIONES_ACTUALIZACION_INDICADOR_01_v1.3.0.md` y `..._v1.4.0.md` describen el comparativo como la "vista inicial". La v1.4.0 agrega las dos gráficas.
- El `README.md`, en la sección "Resultados y trazabilidad", todavía dice que el dashboard incluye la vista de comparación y las gráficas de barras.
- No hay instrucciones para 1.5.x, 1.6.0 ni 1.7.0. Las correcciones 1.6.1 y 1.6.2 solo tratan errores de ejecución.

[COMPROBADO] El comparativo formó parte de las versiones 1.3.0 y 1.4.0, y el proyecto lo documentó así. [SUPUESTO] Eso no indica que deba seguir en 1.7.0. Esa decisión corresponde al responsable del indicador.

Corrección al informe previo (`.agents\tasks\resumen-proyecto-tarifas\informe.md`, punto 2): dice que 1.3.0 y 1.4.0 tienen la sección "con gráficas". Solo 1.4.0 tiene gráficas. El resto del punto 2 se confirma. [COMPROBADO]

## 3. Mini gráficas de tres meses en las tarjetas de 2026

[COMPROBADO] Cada una de las cinco tarjetas de los dashboards 2026 tiene dos mini gráficas de barras:

- **Tarifas mal aplicadas:** número de alertas de cada uno de los tres meses. El pie indica la tendencia del último mes frente al anterior, por ejemplo "Aumenta (+2)".
- **Diferencia neta de alertas:** monto en COP de cada mes. El pie indica cuánto cambió frente al mes anterior.
- Cada barra lleva la etiqueta del mes, por ejemplo "Jun 26". Un mes sin datos se marca "s/d" y su tooltip dice "Sin información".
- No muestran población, registros no evaluables ni la tabla. Esos valores solo quedan en la clave `comparison` de `resultado.json`.

Ejemplos de la corrida 2026-08 del 30/10/2026 (`2026-08_20261030083559`):

| Indicador | Alertas jun / jul / ago | Diferencia neta jun / jul / ago |
|---|---|---|
| IND-01 | 0 / 0 / 2 | COP 0 / 0 / 2.426.530 |
| IND-04 | 2 / 9 / 1 | COP 79.747 / −13.872.267 / −83.027 |

Otro ejemplo: en la corrida 2026-01 del 25/10/2026, IND-04 muestra 4 alertas en 2025-11, "s/d" en 2025-12 y 8 alertas en 2026-01. [COMPROBADO] En la corrida 2026-08 del 30/10/2026, el pie de IND-04 dice "Disminuye (-8)" en alertas y "Aumenta COP 13.789.240" en diferencia. [COMPROBADO]

## 4. Condiciones de activación y disponibilidad de datos

### Activación

- [COMPROBADO] Ninguna condición activa el panel. Las mini gráficas se generan en cada corrida sin condición.
- [COMPROBADO] Un mes cuenta como disponible si su `resultado.json` tiene `period` en formato AAAA-MM, tiene `indicators` y el indicador tiene `data_available` en verdadero (líneas 551 a 609). Un mes con población cero se muestra como "Sin información", aunque su corrida exista.
- [COMPROBADO] Si hay varias corridas del mismo mes, gana la de `generated_at` más reciente. La corrida que se está generando siempre reemplaza su propio mes.

### Corridas disponibles en `resultados\`

| Mes | Corridas con `indicators` | Corrida usada |
|---|---|---|
| 2025-09 | Ninguna | No hay datos |
| 2025-10 | Ninguna | No hay datos |
| 2025-11 | Cuatro de 2025 (1.2.0 dos veces, 1.3.0 y 1.4.0), más la 1.7.0 del 29/10/2026. La 1.0.1 no tiene `indicators`. | La 1.7.0 |
| 2025-12 | Ninguna | No hay datos |
| 2026-01 a 2026-07 | Una por mes (1.7.0, 25/10/2026) | La única |
| 2026-08 | Dos (25/10 y 30/10/2026) | La del 30/10/2026 |

Ventanas de tres meses:

| Mes evaluado | Ventana | Meses con corrida | Resultado |
|---|---|---|---|
| 2025-11 | 2025-09, 2025-10, 2025-11 | 1 de 3 | Dos meses "s/d" |
| 2026-01 | 2025-11, 2025-12, 2026-01 | 2 de 3 | Falta 2025-12 |
| 2026-02 | 2025-12, 2026-01, 2026-02 | 2 de 3 | Falta 2025-12 |
| 2026-03 a 2026-08 | Tres meses calendario | 3 de 3 | Completa |

[COMPROBADO] Los conteos de "Sin información" confirman la tabla: 40 en el dashboard 2025-11 de 1.7.0, 20 en 2026-01 y 2026-02, y 0 desde 2026-03.

### Calidad de la serie

- [COMPROBADO] El dashboard de enero de 2026 muestra el 2025-11 de la corrida 1.4.0 del 23/09/2026: IND-04 con 4 alertas y diferencia neta de COP 2.323.671. La corrida 1.7.0 del 29/10/2026 da 5 alertas y COP 2.323.672.
- [COMPROBADO] La diferencia viene de las fuentes. La corrida 1.4.0 cargó 4 archivos (434 operaciones y 285 adiciones). La corrida 1.7.0 cargó 10 archivos (2.558 operaciones y 484 adiciones).
- [COMPROBADO] Con el código actual y el juego de fuentes de 1.4.0, los cinco indicadores de 2025-11 coinciden con la corrida 1.4.0. IND-04 da 4 alertas, 2 no evaluables y COP 2.323.671,17.
- [SUPUESTO] El código de 1.4.0 no está en el repositorio. Que el código actual reproduzca sus cifras sugiere que la lógica no cambió para este mes, pero no lo demuestra.
- [COMPROBADO] Las corridas del 25/10 de 2026 registraron `Operaciones MCP enero-agosto 2026.xlsx` con 101.407 bytes (SHA-256 `b37b6c…`). Lo comprobé en 2026-01 y en 2026-08. Las corridas del 30/10 y la 1.7.0 de 2025-11 registraron 101.662 bytes (`7f07e9…`), que es el archivo actual.
- [COMPROBADO] En 2026-08, los cinco indicadores son iguales en las dos corridas, pese al cambio de archivo.
- [SUPUESTO] No volví a calcular junio y julio con el archivo nuevo, así que no conozco el efecto del cambio en esos meses.
- [COMPROBADO] La serie de tres meses mezcla corridas hechas en fechas distintas y con fuentes distintas. Mostrar el panel no cambia eso. Solo muestra lo guardado.

## 5. Cambio mínimo: diff verificado, no aplicado

El cambio sale de la copia del prototipo. El archivo del proyecto no se modificó. [COMPROBADO]

Los bloques 1 a 4 se muestran completos. El bloque 5 se describe en texto porque su línea es muy larga y solo cambia su inicio.

```diff
--- a/codigo/indicador_01_tarifas_mcp.py
+++ b/codigo/indicador_01_tarifas_mcp.py
@@ -658,6 +658,6 @@
     valores = {
-        indicador: {fila["Período"]: float(fila.get(clave, 0) or 0) for fila in filas}
+        indicador: {fila["Período"]: (None if fila.get(clave) is None else float(fila[clave])) for fila in filas}
         for indicador, filas in series.items()
     }
-    todos = [valor for indicador in indicadores for valor in valores[indicador].values()] or [0]
+    todos = [valor for indicador in indicadores for valor in valores[indicador].values() if valor is not None] or [0]
     minimo, maximo = min(0.0, min(todos)), max(0.0, max(todos))
@@ -678,3 +678,5 @@
         for indice_periodo, periodo in enumerate(periodos):
-            valor = valores[indicador].get(periodo, 0.0)
+            valor = valores[indicador].get(periodo)
+            if valor is None:
+                continue
             y_valor = margen_sup + (maximo - valor) * escala
@@ -705,3 +707,3 @@
         else:
-            detalle = pd.DataFrame(filas).drop(columns=["_diferencia_neta"], errors="ignore").to_html(index=False, escape=True, classes="data-table", border=0)
+            detalle = pd.DataFrame(filas).drop(columns=["_diferencia_neta", "_disponible"], errors="ignore").astype(object).fillna("Sin información").to_html(index=False, escape=True, classes="data-table", border=0)
         paneles.append(f"<div class=\"card\"><h2>{html.escape(titulo)}</h2><div class=\"table-wrap\">{detalle}</div></div>")
@@ -911,8 +913,9 @@
         metricas[f"IND-0{posicion + 1}"] = resumen
-        botones.append(f'<button class="tab-button{" active" if posicion == 0 else ""}" data-target="{identificador}">IND-0{posicion + 1}</button>')
+        botones.append(f'<button class="tab-button" data-target="{identificador}">IND-0{posicion + 1}</button>')
     series = cargar_comparativo_tres_meses(resultados, config["periodo_evaluado"], metricas)
     for posicion, (titulo, poblacion, estado, diferencia, columnas) in enumerate(vistas):
-        panel, _ = vista_indicador(titulo, poblacion, estado, diferencia, columnas, series[f"IND-0{posicion + 1}"], posicion == 0)
+        panel, _ = vista_indicador(titulo, poblacion, estado, diferencia, columnas, series[f"IND-0{posicion + 1}"], False)
         paneles.append(panel)
-    comparativo = ""
+    titulos_comparativo = {f"IND-0{posicion + 1}": titulo for posicion, (titulo, *_) in enumerate(vistas)}
+    comparativo = panel_comparativo_tres_meses(series, titulos_comparativo)
     fuentes_html = "".join(f"<li>{html.escape(p.name)}</li>" for p in fuentes)
```

Bloque 5, línea 922 (cadena HTML del documento). Antes: `<div class="toolbar"><nav>{''.join(botones)}</nav>`. Después: `<div class="toolbar"><nav><button class="tab-button active" data-target="comparativo">Comparativo 3 meses</button>{''.join(botones)}</nav>`. El resto de la línea no cambia.

Qué hace cada bloque:

1. **Tabla del panel (línea 707).** Quita la columna técnica `_disponible` y muestra "Sin información" en los meses sin dato. Sin este cambio, el panel de 2025-11 tiene 40 celdas "NaN" y 5 columnas `_disponible`, medido en la copia. `astype(object)` evita un aviso de pandas 3.1 al rellenar texto sobre columnas numéricas. [COMPROBADO]
2. **Gráfica agrupada (líneas 658 a 679).** Un mes sin dato no dibuja barra ni tooltip. Sin este cambio, la función muestra "IND-01 · 2025-09: 0" y "IND-01 · 2025-10: 0", que parecen ceros reales. [COMPROBADO]
3. **Pestañas (líneas 912 y 915).** IND-01 deja de estar activa al cargar. Solo queda visible el comparativo. [COMPROBADO]
4. **Llamada y botón (líneas 917 y 922).** Se llama `panel_comparativo_tres_meses` con la serie que ya se calcula, y se agrega el botón "Comparativo 3 meses" como primera pestaña. [COMPROBADO]

Lo que no cambia: `cargar_datos`, `recalcular`, `tarifa_para`, `tarifa_aplicada`, `ejecutar`, `exportar_excel`, `exportar_pdf` y `resultado.json`. El cambio no toca ninguna de esas funciones. [COMPROBADO]

Aviso preexistente: `tabla()` (línea 471) usa `fillna("No suministrado")` sobre columnas numéricas. Con pandas 3.1 emite `Pandas4Warning` cuando hay celdas vacías, y el aviso dice que en una versión futura será un error. Vi el aviso en la corrida con el juego de fuentes de 1.4.0. No cambia resultados hoy, y el cambio mínimo no lo corrige. [COMPROBADO]

## 6. Verificación

Método. [COMPROBADO]

1. Copié el código y las fuentes a `.agents\verificacion\hallazgo_tres_meses\original\` y `...\parche\`, con sus carpetas `resultados`.
2. Apliqué el cambio solo a la copia `parche` con un script que exige que cada patrón aparezca exactamente una vez.
3. Ejecuté ambas copias con `--periodo 2025-11` y `--periodo 2026-08`. Las cuatro corridas terminaron con código 0.
4. Comparé resultados, XLSX, metadatos y HTML. Luego borré el prototipo.

| Comprobación | 2025-11 | 2026-08 |
|---|---|---|
| `resultado.json` igual (indicators, comparison, metrics), sin campos de tiempo | Sí | Sí |
| `detalle_calculo.json` igual (SHA-256) | Sí | Sí |
| Valores de todas las hojas del XLSX | Sí | Sí |
| Metadatos (fuentes, configuración, control de carga, notas) | Sí | Sí |
| Paneles IND-01 a IND-05 iguales (sin clase de activación) | Sí | Sí |
| Filas de datos en el comparativo (5 tablas) | 15 | 15 |
| Celdas NaN, original → parche | 40 → 0 | 0 → 0 |
| Columna `_disponible`, original → parche | 5 → 0 | 5 → 0 |
| Barras con tooltip "0" en meses sin dato, original → parche | Sí → No | No aplica |
| Pestaña activa en el parche | Comparativo 3 meses | Comparativo 3 meses |

Además, el código actual con el juego de fuentes de 1.4.0 reproduce las cifras de esa versión (sección 4). [COMPROBADO]

Qué no verifiqué. [COMPROBADO salvo donde se indica]

- No abrí el HTML en un navegador. La revisión fue por estructura y texto.
- Probé un mes de 2026 (agosto) y uno de 2025 (noviembre). No corrí el parche para los demás meses.
- [SUPUESTO] El aspecto visual de la pestaña, el tamaño de las gráficas y los saltos de página al imprimir no se revisaron.
- No corrí las pruebas unitarias del proyecto con el parche. Según `.agents\verificacion\registro_referencia.md`, antes del cambio fallaban `test_excel_y_pdf` y `test_conversion_decimal_incoherente`. Quien aplique el cambio debe comparar contra esa línea base.

## 7. Decisiones para el responsable

1. **¿Debe volver el comparativo?** Si sí, aplicar el cambio de la sección 5. Si no, eliminar `panel_comparativo_tres_meses`, `grafico_comparativo` y la asignación de la línea 917, y corregir el README. [SUPUESTO sobre el alcance]
2. **¿Qué pestaña debe abrir primero?** El cambio supone el comparativo, como en 1.3.0 y 1.4.0. Si se prefiere IND-01, hay que quitar la clase `active` del botón comparativo y del panel.
3. **¿Cómo se quiere tratar la serie histórica?** Hoy mezcla corridas de fechas y fuentes distintas (sección 4). [SUPUESTO] Recalcular los meses con un juego de fuentes fijo daría una serie consistente, pero cambiaría algunas cifras ya guardadas, como la de IND-04 en 2025-11.

## 8. Archivos revisados

- No modificados: `codigo\indicador_01_tarifas_mcp.py`, `pruebas\test_ejecucion_mensual.py`, `README.md`, `INSTRUCCIONES_ACTUALIZACION_INDICADOR_01_v1.2.0.md`, `..._v1.3.0.md`, `..._v1.4.0.md`, `INSTRUCCIONES_v1.6.1.md`, `INSTRUCCIONES_v1.6.2.md`, las 15 carpetas de `resultados\` y `.agents\tasks\resumen-proyecto-tarifas\informe.md`.
- Estado del proyecto después de la investigación: sin cambios. El hash de `codigo\indicador_01_tarifas_mcp.py` sigue en `195E128F…`, no hay `__pycache__`, `resultados\` tiene 15 carpetas y 116 archivos, y la raíz tiene las mismas 15 entradas.
