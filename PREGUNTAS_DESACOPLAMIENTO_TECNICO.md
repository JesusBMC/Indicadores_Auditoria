# Preguntas TÉCNICAS + LÓGICA para desacoplar el Indicador 01
## Sobre estructura de código, lógica de negocio y arquitectura

---

## 1. LÓGICA DE ACUMULADOS Y PERÍODO

### 1.1 Definición de acumulado
- **En `clasificar_adiciones()` y `recalcular()`, veo `anio_acumulado = fecha_evento.dt.year`**
  - ¿El acumulado es **siempre anual** (enero a diciembre del mismo año)?
  - ¿O hay casos donde se acumula por período fiscal, trimestre, o semestre?
  - ¿El rango es fijo o configurable?

### 1.2 Cálculo de acumulado_previo
- **En `recalcular()`, el acumulado se suma iterativamente por grupo:**
  ```python
  for indice, fila in grupo.iterrows():
      datos.at[indice, "acumulado_previo"] = acumulado
      acumulado += fila["valor_base"]
  ```
  - ¿Este acumulado es **solo para el mes actual**, o incluye histórico desde enero?
  - ¿Las operaciones se ordenan por `fecha_evento`, lo que significa que enero siempre empieza en 0?
  - ¿O si ejecutas febrero, el `acumulado_previo` de febrero incluye enero?
  - **¿Eso es lo que causa el bloqueo en enero 2026?** No poder leer enero 2026 genera acumulado 0, pero ¿es eso correcto?

### 1.3 Agregación por mandante + naturaleza + año
- **¿Por qué se agrupa por `["mandante_compra", "anio_acumulado", "naturaleza"]`?**
  - ¿El acumulado es **por mandante independiente**? (cada mandante acumula sus propios valores)
  - ¿O hay un acumulado global que se distribuye?
  - ¿Qué ocurre si un mandante cambia dentro del año?

### 1.4 Dependencia de datos previos
- **¿Un mes nuevo (ej: enero 2026) necesita datos de diciembre 2025?**
  - Si ejecutas enero 2026 sin diciembre 2025 en las fuentes, ¿el acumulado_previo de enero será 0?
  - ¿O falla porque no puede reconstruir correctamente?
  - ¿Eso es un error o un comportamiento esperado?
  - **¿Si enero empieza en 0, puede haber tarifas incorrectas por rangos de acumulado?**

---

## 2. LÓGICA DE CLASIFICACIÓN DE ADICIONES

### 2.1 Reglas de negocio para adiciones
- **En `clasificar_adiciones()`, hay reglas rígidas:**
  ```python
  hasta_30 = disponible & resultado["dias_diferencia_entrega"].between(0, 30)
  resultado.loc[hasta_30, "naturaleza"] = "Disponible"
  
  mas_30 = disponible & resultado["dias_diferencia_entrega"].gt(30)
  resultado.loc[mas_30, "naturaleza"] = "Forward"
  ```
  - ¿El umbral de 30 días es **fijo o configurable**?
  - ¿Hay excepciones según el tipo de mandante o negocio?
  - ¿Quién define estas reglas? ¿Están en `configuracion_ejecucion.json` o hardcoded?
  - **¿Pueden separarse estas reglas en un módulo independiente?**

### 2.2 Adiciones sin original
- **¿Qué significa una adición sin operación original?**
  - `original_naturaleza = NA` → `estado_clasificacion = "No evaluable"`
  - ¿Esto es un error de datos o un caso esperado?
  - ¿Debería bloquearse la corrida o solo alertarse?
  - **¿Cuántas adiciones sin original son "aceptables"?**

### 2.3 Fecha de evento vs fecha de operación
- **En adiciones:**
  ```python
  resultado["fecha_evento"] = resultado["fecha_solicitud"]
  resultado["anio_acumulado"] = resultado["fecha_solicitud"].dt.year
  ```
  - ¿Por qué usa `fecha_solicitud` en lugar de `fecha_operacion`?
  - ¿Esto significa que una adición en diciembre 2025 para una operación de enero 2026 se acumula en 2025?
  - **¿Eso es correcto o un bug?**

---

## 3. LÓGICA DE TARIFAS Y BÚSQUEDA

### 3.1 Función `tarifa_para()`
- **¿Cómo se selecciona la tarifa correcta?**
  ```python
  candidato = t.loc[(acumulado_previo > t["minimo"]) & (acumulado_previo <= t["maximo"])]
  if acumulado_previo == 0:
      candidato = t.loc[t["minimo"].eq(0)]
  ```
  - ¿Hay rangos de acumulado con tarifas diferentes? (ej: 0-100M, 100-500M, etc.)
  - ¿El rango inferior es inclusive? ¿Qué ocurre en los límites exactos?
  - ¿Si no hay tarifa en ese rango, qué pasa? (parece que retorna `None`)
  - **¿Puedo extraer la búsqueda de tarifa a una función de tabla independiente?**

### 3.2 Tarifas por punta
- **¿Por qué hay tarifas distintas para Comprador y Vendedor?**
  - ¿Son siempre diferentes o a veces iguales?
  - ¿Quién proporciona estas tarifas? (¿el PT Inventario CUB?)
  - **¿La punta está en operaciones o se deduce?**

### 3.3 Compensación y liquidación (CyL)
- **¿Por qué CyL no usa el acumulado?**
  ```python
  if servicio == "Compensación y liquidación" or punta == "Vendedor":
      return t.iloc[0]
  ```
  - ¿CyL tiene una tarifa fija, sin rangos de acumulado?
  - ¿Es la misma para todos los mandantes y naturalezas?
  - **¿CyL y Registro de operación son servicios independientes o relacionados?**

### 3.4 Artículo CUB y página
- **¿De dónde vienen `articulo_cub` y `pagina_cub`?**
  ```python
  datos.at[indice, "articulo_cub"] = texto_trazabilidad(compra["articulo_cub"])
  ```
  - ¿Vienen del PT Inventario y se usan solo para auditoría?
  - ¿O es información crítica para la validación?
  - **¿Se pueden separar en un anexo sin afectar el cálculo principal?**

---

## 4. LÓGICA DE EVALUACIÓN Y ALERTAS

### 4.1 Tolerancia
- **¿Qué es exactamente `tolerancia_cop`?**
  ```python
  alerta = datos[diferencia].abs().gt(tolerancia) & ~no_evaluable
  ```
  - ¿Es una cantidad en COP (ej: $100)?
  - ¿O un porcentaje?
  - ¿Se aplica a todos los servicios (Registro + CyL) de la misma forma?
  - **¿Debería haber tolerancias diferentes por servicio o mandante?**

### 4.2 Estados posibles
- **¿Existen exactamente 3 estados?**
  - `Conforme`: diferencia ≤ tolerancia
  - `Alerta`: diferencia > tolerancia
  - `No evaluable`: faltan datos
  - ¿O hay otros? (ej: `Pendiente de información`, `Error crítico`)

### 4.3 Clasificación "No evaluable"
- **¿Por qué una adición no evaluable no falla?**
  ```python
  no_evaluable = clasificacion_no_evaluable | datos[aplicado].isna() | datos[esperado].isna()
  datos.loc[no_evaluable, estado] = "No evaluable"
  ```
  - ¿Se reporta en el resultado final?
  - ¿El usuario debe revisarlas manualmente?
  - **¿Hay un umbral de % de "No evaluable" que falle la corrida?**

### 4.4 Resultado compuesto (CyL)
- **¿Por qué se combinan los resultados de Compra y Venta?**
  ```python
  datos.loc[datos[["resultado_cyl_compra", "resultado_cyl_venta"]].eq("Alerta").any(axis=1), "resultado_cyl"] = "Alerta"
  parcial_cyl = ... eq("No evaluable").any(axis=1)
  datos.loc[parcial_cyl & datos["resultado_cyl"].ne("Alerta"), "resultado_cyl"] = "No evaluable"
  ```
  - ¿Basta que una punta (Compra O Venta) tenga alerta para que CyL sea alerta?
  - ¿Si ambas son "No evaluable", qué reportas?
  - **¿Se puede cambiar esta lógica sin romper el sistema?**

---

## 5. LÓGICA DE OPERACIONES ORIGINALES vs ADICIONES

### 5.1 Descarte de operaciones
- **En `preparar_originales()`, hay descarte:**
  ```python
  mcp = operaciones.loc[operaciones["naturaleza"].notna()].copy()
  descartadas = operaciones.loc[operaciones["negocio"].isin(EXCLUIDOS)].copy()
  ```
  - ¿Las operaciones sin naturaleza se descartan o se procesan de otra forma?
  - ¿Qué es `EXCLUIDOS`? ¿Está hardcoded o es configurable?
  - **¿`EXCLUIDOS` debería estar en `configuracion_ejecucion.json`?**

### 5.2 Coherencia de operación original
- **¿Qué significa "firma" y por qué se valida?**
  ```python
  firma = grupo[CRITICOS_ORIGINAL].astype(str).drop_duplicates()
  if len(firma) > 1:
      # Inconsistente
  ```
  - ¿`CRITICOS_ORIGINAL` son campos que no deben cambiar entre registros de la misma operación?
  - ¿Qué campos son críticos? (naturaleza, mandante, fecha, etc.)
  - **¿Dónde está definida `CRITICOS_ORIGINAL`?** (no veo en el código leído)

### 5.3 Búsqueda de original para adiciones
- **¿La búsqueda de original es exacta?**
  ```python
  lookup = originales.set_index("operacion")
  resultado[f"original_{campo}"] = resultado["operacion"].map(lookup[campo])
  ```
  - ¿Solo busca por ID de operación?
  - ¿Qué si hay múltiples originales con el mismo ID?
  - **¿Se puede cachar esta búsqueda para no hacerla en cada corrida?**

---

## 6. LÓGICA DE DATOS FALTANTES

### 6.1 Archivos no leídos
- **¿Por qué algunos archivos XLS/XLSB no se leen?**
  ```python
  ignorados = [str(p.relative_to(raiz)) for carpeta in (ops_dir, adi_dir) 
               for p in sorted(carpeta.iterdir()) if p.suffix.lower() in {".xls", ".xlsb"}]
  ```
  - ¿Es una limitación técnica (pandas solo lee XLSX)?
  - ¿O es intencional para evitar formatos antiguos?
  - **¿Debería dar error o solo advertir?**
  - **¿Se puede parametrizar?**

### 6.2 Columnas faltantes
- **¿Qué sucede si un XLSX no tiene todas las columnas requeridas?**
  ```python
  faltan = [c for c in requeridas if c not in columnas]
  if faltan:
      raise ValueError(...)
  ```
  - ¿Falla la ejecución completa?
  - ¿O solo ese archivo se descarta?
  - **¿Debería alertarse antes de cargar todo?**

### 6.3 Fechas inválidas
- **¿Qué sucede con fechas que no pueden convertirse?**
  ```python
  "fecha_operacion": pd.to_datetime(df[columnas["fechaoperacion"]], errors="coerce")
  ```
  - `errors="coerce"` convierte inválidas a `NaT`
  - Esos registros quedan sin año → no se evalúan
  - ¿Es silencioso o se advierte al usuario?
  - **¿Hay un contador de fechas inválidas?**

---

## 7. LÓGICA DE HISTÓRICOS E INCONSISTENCIAS

### 7.1 Control de históricos
- **¿Por qué se validan históricos por separado?**
  ```python
  historicos = eventos.loc[~eventos["tipo_registro"].eq("Operación") 
                          | (eventos["fecha_operacion"].dt.to_period("M") != periodo)]
  inconsistencias_historicas = incoherencias_coherencia_base(historicos)
  ```
  - ¿Los históricos se validan con los mismos criterios que el mes actual?
  - ¿O hay reglas diferentes?
  - **¿Puede hacerse esta validación una sola vez al año, no en cada corrida?**

### 7.2 Función `incoherencias_coherencia_base()`
- **¿Qué validaciones hace?**
  - Compara `valor_base`, `tarifa_reportada`, `cobro_aplicado`
  - ¿Qué tolerancia usa? ¿Es la misma que `tolerancia_cop`?
  - ¿Por qué se valida solo en históricos, no en el mes actual?
  - **¿Es redundante con `validar_coherencia_base()`?**

### 7.3 Reportes de avisos
- **¿Los avisos se generan pero no detienen la corrida?**
  ```python
  if not inconsistencias_historicas.empty:
      avisos.append(f"Control histórico: ...")
  ```
  - ¿Un histórico inconsistente es un error o una advertencia?
  - ¿Debería remediar el dato o solo alertar?
  - **¿Hay un nivel de severidad de avisos?**

---

## 8. LÓGICA DE CONSOLIDADO ANUAL

### 8.1 Comparativo de 3 meses
- **¿Por qué exactamente 3 meses?**
  ```python
  periodos = [str(periodo_limite - n) for n in (2, 1, 0)]  # -2, -1, 0
  ```
  - ¿Siempre 2 anteriores + actual?
  - ¿O es flexible según el período?
  - **¿Puede ser 1-2 meses si no existen anteriores?**

### 8.2 Lectura de `resultado.json`
- **¿Cada corrida se almacena en su propio `resultado.json`?**
  - ¿Cómo evita conflictos si re-ejecutas el mismo mes?
  - ¿La carpeta se sobrescribe o se crea una nueva?
  - **¿Varias carpetas del mismo mes en `resultados/`?**

### 8.3 Agregación mensual
- **¿Cómo se resumen todas las alertas de un mes en 1 fila del consolidado?**
  - ¿Suma de alertas?
  - ¿Promedio de diferencias netas?
  - ¿Máximo de diferencia?
  - **¿Se pueden desacoplar estas agregaciones?**

### 8.4 Cargar comparativo vs generar consolidado
- **¿Son dos procesos independientes?**
  - `cargar_comparativo_tres_meses()` se llama en `html_reporte_v2()`
  - `generar_consolidado_alertas_anual.py` es un script separado
  - **¿Se pueden unificar o son propósitos distintos?**

---

## 9. PUNTOS DE ACOPLAMIENTO EN EL CÓDIGO

### 9.1 `cargar_datos()` → lectura de archivos
- **Hoy:** Lee todos los XLSX y concatena
- **Problema:** Bloquea en enero 2026 porque intenta procesar 2022-2026
- **Cambio necesario:** ¿Podemos leer solo el período solicitado + N meses anteriores?
- **Pregunta:** ¿Cuál es el N mínimo? (1 mes, 3 meses, 12 meses)

### 9.2 `ejecutar()` → validación inmediata
- **Hoy:** Valida coherencia de TODO antes de calcular
- **Cambio:** ¿Validar solo el mes solicitado? ¿O permitir validación posterior?
- **Pregunta:** ¿Se puede separar `validar_datos()` de `ejecutar()`?

### 9.3 `cargar_comparativo_tres_meses()` → dependencia de histórico
- **Hoy:** Lee todos los `resultado.json` previos
- **Cambio:** ¿Cachear comparativos? ¿O hacerlos opcionales?
- **Pregunta:** ¿El comparativo es crítico o solo informativo?

### 9.4 `generar_consolidado_alertas_anual.py` → recálculo total
- **Hoy:** Lee todas las carpetas `resultados/`
- **Cambio:** ¿Incremental desde último consolidado?
- **Pregunta:** ¿Cada mes actualiza el consolidado o se recalcula?

### 9.5 Interdependencias
- **¿`recalcular()` depende de orden de ejecución?** (sí, por acumulados)
- **¿`clasificar_adiciones()` depende de `preparar_originales()`?** (sí, by lookup)
- **¿Se pueden ejecutar en paralelo o en orden?**

---

## 10. FLUJO DE CONTROL ACTUAL vs NECESARIO

### 10.1 Flujo actual
```
main() 
  → cargar_configuracion()
  → cargar_datos() [CUELLOS DE BOTELLA]
    → leer_operaciones() [lee 2022-2026]
    → leer_adiciones() [lee 2022-2026]
    → extraer_tarifas()
    → preparar_originales()
    → clasificar_adiciones()
  → validar_coherencia_base() [TODO histórico]
  → recalcular() [acumulados por año]
  → html_reporte_v2()
    → cargar_comparativo_tres_meses() [busca resultado.json]
  → exportar_excel()
  → exportar_pdf()
```

### 10.2 Flujo deseado (sin bloqueos)
- ¿Cargar solo último 12 meses + período solicitado?
- ¿Validaciones opcionales o en background?
- ¿Caché de acumulados previos?
- ¿Comparativo generado on-demand sin buscar archivos?

---

## 11. CONSTANTES Y CONFIGURACIÓN HARDCODED

### 11.1 Constantes definidas
- **`EXCLUIDOS`:** ¿Dónde está? (no la veo)
- **`MCP_CODIGOS`:** Mapeo de negocio → naturaleza ¿Es fijo o configurable?
- **`CRITICOS_ORIGINAL`:** Campos a validar ¿Dónde está?
- **Umbral de 30 días:** ¿En adiciones, debería estar en config?
- **Tolerancia:** ¿Siempre desde `configuracion_ejecucion.json`?

### 11.2 ¿Dónde están estas constantes?
- ¿Al inicio del archivo?
- ¿En una base de datos?
- ¿En `configuracion_ejecucion.json`?
- **¿Podrían estar en un módulo separado `reglas_negocio.py`?**

---

## 12. PREGUNTAS FINALES PARA DESACOPLAR

1. **¿Es el acumulado SIEMPRE anual?** Si no, ¿hay configuración?
2. **¿Un mes se puede procesar SIN datos de meses anteriores?** ¿Con acumulado 0?
3. **¿Las reglas de clasificación (30 días) están en código o config?**
4. **¿Hay un esquema de datos oficial** (JSON Schema, ER, doc) o solo el código?
5. **¿Los `resultado.json` son finales o se heredan datos de ellos?**
6. **¿Meses en paralelo o siempre secuencial?**
7. **¿Qué es verdaderamente "crítico" vs. "informativo"?**
8. **¿Cuál es el caso de uso principal: mensual, anual, o ad-hoc?**
9. **¿Se pueden separar cálculo de reporte sin perder funcionalidad?**
10. **¿Se pueden cachear resultados de adiciones, tarifas, acumulados?**
