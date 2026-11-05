#!/usr/bin/env python3
"""Indicador 01: validación continua de tarifas de registro MCP.

La aplicación se ejecuta desde la carpeta raíz y utiliza únicamente:
  fuentes/operaciones/  : bases anuales y mensuales de operaciones
  fuentes/adiciones/    : base de adiciones
  fuentes/parametros/   : PT de tarifas CUB y configuración de la corrida
  resultados/           : salidas inmutables por ejecución

La salida incluye dashboard HTML, PDF, Excel y JSON por cada ejecución.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

VERSION = "1.7.0"
MCP_CODIGOS = {"DISMCP": "Disponible", "FRWMCP": "Forward"}
EXCLUIDOS = {"DISPSG", "FWRDSG", "FWRD"}
CRITICOS_ORIGINAL = ["negocio", "fecha_entrega_original", "mandante_compra"]


def normalizar(texto: object) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


def id_operacion(valor: object) -> str:
    """Estandariza 77869074.C y 77869074 como 77869074 sin alterar otros IDs."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    texto = re.sub(r"\.0$", "", texto)
    return re.sub(r"\.[A-Za-z]+$", "", texto).strip()


def numero(valor: object) -> float:
    if pd.isna(valor) or str(valor).strip() in {"", "-", "$ -"}:
        return float("nan")
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).replace("COP", "").replace("$", "").replace(" ", "")
    if not texto or set(texto) <= {"-"}:
        return float("nan")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") else texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def porcentaje(valor: object) -> float:
    if pd.isna(valor):
        return float("nan")
    original = str(valor).strip()
    texto = original.replace("%", "")
    n = numero(texto)
    return n / 100 if "%" in original or n > 1 else n


def money(valor: object) -> str:
    return "No suministrado" if pd.isna(valor) else f"COP {float(valor):,.0f}".replace(",", ".")


def pct(valor: object) -> str:
    return "No suministrado" if pd.isna(valor) else f"{float(valor) * 100:.3f}%".replace(".", ",")


ETIQUETAS_COLUMNAS = {
    "tipo_registro": "Tipo de registro", "operacion": "Operación", "no_adicion": "No. adición",
    "negocio": "Negocio", "naturaleza": "Naturaleza", "original_naturaleza": "Naturaleza original",
    "mandante_compra": "Mandante comprador", "fecha_operacion": "Fecha de operación",
    "fecha_evento": "Fecha del evento", "fecha_solicitud": "Fecha de solicitud",
    "fecha_entrega_original": "Fecha entrega original", "fecha_entrega_adicion": "Fecha entrega adición",
    "original_fecha_entrega_original": "Fecha entrega original", "dias_diferencia_entrega": "Días diferencia entrega",
    "regla_aplicada": "Regla aplicada", "acumulado_previo": "Acumulado previo",
    "valor_base": "Valor base", "archivo_operacion": "Archivo de operación", "archivo_adicion": "Archivo de adición",
}


def etiqueta_columna(campo: str) -> str:
    if campo in ETIQUETAS_COLUMNAS:
        return ETIQUETAS_COLUMNAS[campo]
    etiquetas = [
        ("tarifa_cyl_compra", "Tarifa CyL compra"), ("tarifa_cyl_venta", "Tarifa CyL venta"),
        ("tarifa_compra", "Tarifa compra"), ("tarifa_venta", "Tarifa venta"),
        ("cyl_compra", "CyL compra"), ("cyl_venta", "CyL venta"),
        ("registro_compra", "Registro compra"), ("registro_venta", "Registro venta"),
        ("diferencia_cyl", "Diferencia CyL"), ("diferencia_compra", "Diferencia compra"),
        ("diferencia_venta", "Diferencia venta"), ("resultado_", "Resultado "),
        ("motivo_", "Motivo "),
    ]
    for prefijo, etiqueta in etiquetas:
        if campo.startswith(prefijo):
            sufijo = campo[len(prefijo):].replace("_", " ").strip()
            return (etiqueta + (" " + sufijo if sufijo else "")).strip().capitalize()
    return campo.replace("_", " ").capitalize()


def texto_trazabilidad(valor: object) -> str:
    """Mantiene la trazabilidad CUB como texto en pandas con dtype estricto."""
    return "" if pd.isna(valor) else str(valor)


def tarifa_aplicada(valor_registro: object, valor_base: object) -> float:
    """Calcula la tarifa efectivamente cobrada, sin depender de una columna opcional.

    Las operaciones normalmente incluyen el porcentaje reportado por el sistema,
    mientras que las adiciones no. Por consistencia, la tarifa real de ambas
    poblaciones se obtiene del valor de registro cobrado dividido entre el valor
    base del evento.
    """
    if pd.isna(valor_registro) or pd.isna(valor_base) or float(valor_base) == 0:
        return float("nan")
    return float(valor_registro) / float(valor_base)


def fila_encabezado(ruta: Path, requerido: str, hoja: str | int = 0) -> int:
    bruto = pd.read_excel(ruta, sheet_name=hoja, header=None, nrows=30, dtype=object)
    objetivo = normalizar(requerido)
    for indice, fila in bruto.iterrows():
        if objetivo in {normalizar(x) for x in fila.tolist() if pd.notna(x)}:
            return int(indice)
    raise ValueError(f"No se encontró el encabezado '{requerido}' en {ruta.name}.")


def leer_operaciones(ruta: Path) -> pd.DataFrame:
    cabecera = fila_encabezado(ruta, "NumeroOperacion")
    df = pd.read_excel(ruta, header=cabecera, dtype=object)
    columnas = {normalizar(c): c for c in df.columns}
    requeridas = ["numerooperacion", "negocio", "fechaoperacion", "fechaentregafin", "mandantecompra", "valornegocio", "valorregistroc", "valorregistrov"]
    faltan = [c for c in requeridas if c not in columnas]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan columnas {', '.join(faltan)}.")
    salida = pd.DataFrame({
        "operacion": df[columnas["numerooperacion"]].map(id_operacion),
        "negocio": df[columnas["negocio"]].astype(str).str.upper().str.strip(),
        "fecha_operacion": pd.to_datetime(df[columnas["fechaoperacion"]], errors="coerce"),
        "fecha_entrega_original": pd.to_datetime(df[columnas["fechaentregafin"]], errors="coerce"),
        "mandante_compra": df[columnas["mandantecompra"]].map(id_operacion),
        "valor_base": df[columnas["valornegocio"]].map(numero),
        "registro_compra_aplicado": df[columnas["valorregistroc"]].map(numero),
        "registro_venta_aplicado": df[columnas["valorregistrov"]].map(numero),
        "tarifa_compra_reportada": df[columnas["porcregistroc"]].map(porcentaje) if "porcregistroc" in columnas else float("nan"),
        "tarifa_venta_reportada": df[columnas["porcregistrov"]].map(porcentaje) if "porcregistrov" in columnas else float("nan"),
        "cyl_compra_aplicado": df[columnas["valorcamarac"]].map(numero) if "valorcamarac" in columnas else float("nan"),
        "cyl_venta_aplicado": df[columnas["valorcamarav"]].map(numero) if "valorcamarav" in columnas else float("nan"),
        "archivo_operacion": ruta.name,
    })
    salida["tarifa_compra_aplicada"] = [
        tarifa_aplicada(registro, base)
        for registro, base in zip(salida["registro_compra_aplicado"], salida["valor_base"])
    ]
    salida["tarifa_venta_aplicada"] = [
        tarifa_aplicada(registro, base)
        for registro, base in zip(salida["registro_venta_aplicado"], salida["valor_base"])
    ]
    salida["tarifa_cyl_compra_aplicada"] = [
        tarifa_aplicada(cobro, base)
        for cobro, base in zip(salida["cyl_compra_aplicado"], salida["valor_base"])
    ]
    salida["tarifa_cyl_venta_aplicada"] = [
        tarifa_aplicada(cobro, base)
        for cobro, base in zip(salida["cyl_venta_aplicado"], salida["valor_base"])
    ]
    salida = salida.loc[salida["operacion"].ne("")].copy()
    salida["naturaleza"] = salida["negocio"].map(MCP_CODIGOS)
    salida["anio_acumulado"] = salida["fecha_operacion"].dt.year
    salida["tipo_registro"] = "Operación"
    salida["fecha_evento"] = salida["fecha_operacion"]
    return salida


def leer_adiciones(ruta: Path) -> pd.DataFrame:
    cabecera = fila_encabezado(ruta, "Operacion")
    df = pd.read_excel(ruta, header=cabecera, dtype=object)
    columnas = {normalizar(c): c for c in df.columns}
    requeridas = ["operacion", "valoradicion", "noadicion", "registrocompra", "registroventa", "fechasolicitud", "fechaentrega"]
    faltan = [c for c in requeridas if c not in columnas]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan columnas {', '.join(faltan)}.")
    salida = pd.DataFrame({
        "operacion": df[columnas["operacion"]].map(id_operacion),
        "no_adicion": df[columnas["noadicion"]].map(id_operacion),
        "valor_base": df[columnas["valoradicion"]].map(numero),
        "registro_compra_aplicado": df[columnas["registrocompra"]].map(numero),
        "registro_venta_aplicado": df[columnas["registroventa"]].map(numero),
        "cyl_compra_aplicado": df[columnas["cylcompra"]].map(numero) if "cylcompra" in columnas else float("nan"),
        "cyl_venta_aplicado": df[columnas["cylventa"]].map(numero) if "cylventa" in columnas else float("nan"),
        "iva_registro_compra": df[columnas["ivaregistrocompra"]].map(numero) if "ivaregistrocompra" in columnas else float("nan"),
        "iva_registro_venta": df[columnas["ivaregistroventa"]].map(numero) if "ivaregistroventa" in columnas else float("nan"),
        "fecha_solicitud": pd.to_datetime(df[columnas["fechasolicitud"]], errors="coerce"),
        "fecha_entrega_adicion": pd.to_datetime(df[columnas["fechaentrega"]], errors="coerce"),
        "archivo_adicion": ruta.name,
    }).loc[lambda x: x["operacion"].ne("")].copy()
    salida["tarifa_compra_aplicada"] = [
        tarifa_aplicada(registro, base)
        for registro, base in zip(salida["registro_compra_aplicado"], salida["valor_base"])
    ]
    salida["tarifa_venta_aplicada"] = [
        tarifa_aplicada(registro, base)
        for registro, base in zip(salida["registro_venta_aplicado"], salida["valor_base"])
    ]
    salida["tarifa_cyl_compra_aplicada"] = [
        tarifa_aplicada(cobro, base)
        for cobro, base in zip(salida["cyl_compra_aplicado"], salida["valor_base"])
    ]
    salida["tarifa_cyl_venta_aplicada"] = [
        tarifa_aplicada(cobro, base)
        for cobro, base in zip(salida["cyl_venta_aplicado"], salida["valor_base"])
    ]
    return salida


def hoja_y_encabezado_tarifas(ruta: Path) -> tuple[str, int]:
    """Ubica el inventario CUB o la hoja de detalle del PT, sin fijar la fila.

    El inventario original usa la hoja ``Inventario`` y encabezados en la primera
    fila. El PT de entendimiento utiliza ``Detalle tarifas`` y deja los
    encabezados en una fila posterior. Ambos formatos son fuentes oficiales
    válidas y deben poder utilizarse sin modificar el archivo suministrado.
    """
    libro = pd.ExcelFile(ruta)
    nombres = {normalizar(nombre): nombre for nombre in libro.sheet_names}
    for candidato in ("inventario", "detalletarifas"):
        if candidato not in nombres:
            continue
        hoja = nombres[candidato]
        bruto = pd.read_excel(ruta, sheet_name=hoja, header=None, nrows=30, dtype=object)
        for indice, fila in bruto.iterrows():
            campos = {normalizar(x) for x in fila.tolist() if pd.notna(x)}
            tiene_tarifa = any(campo == "tarifa" or campo.startswith("tarifa") for campo in campos)
            requeridos = {"mercadosistema", "productoservicio", "modalidadsegmento", "responsabledelpago", "articulocub"}
            tiene_pagina = "paginapdf" in campos or "paginacub" in campos
            if requeridos.issubset(campos) and tiene_tarifa and tiene_pagina:
                return hoja, int(indice)
    raise ValueError(
        f"{ruta.name}: no se encontró una hoja de tarifas compatible. "
        "Se esperaba 'Inventario' o 'Detalle tarifas' con los campos de mercado, producto, modalidad y tarifa."
    )


def columna_tarifa(columnas: dict[str, object], campo: str) -> object:
    """Obtiene un campo exacto o, para tarifa, uno que inicie con el nombre."""
    if campo in columnas:
        return columnas[campo]
    if campo == "tarifa":
        for nombre, original in columnas.items():
            if nombre.startswith("tarifa"):
                return original
    if campo == "paginapdf" and "paginacub" in columnas:
        return columnas["paginacub"]
    raise KeyError(campo)


def extraer_tarifas(ruta: Path) -> pd.DataFrame:
    hoja, cabecera = hoja_y_encabezado_tarifas(ruta)
    df = pd.read_excel(ruta, sheet_name=hoja, header=cabecera, dtype=object)
    c = {normalizar(x): x for x in df.columns}
    requeridas = ["mercadosistema", "productoservicio", "modalidadsegmento", "responsabledelpago", "tarifa", "articulocub", "paginapdf"]
    try:
        columnas = {campo: columna_tarifa(c, campo) for campo in requeridas}
    except KeyError:
        raise ValueError(f"{ruta.name}: la hoja {hoja!r} no tiene la estructura esperada.") from None
    base = df.loc[df[columnas["mercadosistema"]].astype(str).str.upper().eq("MCP")].copy()
    filas = []
    for _, fila in base.iterrows():
        producto = normalizar(fila[columnas["productoservicio"]])
        modalidad = str(fila[columnas["modalidadsegmento"]])
        naturaleza = "Forward" if "forward" in modalidad.lower() else "Disponible" if "disponible" in modalidad.lower() else None
        servicio = "Registro de operación" if "registrodeoperacion" in producto else "Compensación y liquidación" if "serviciodecompensacionyliquidacion" in producto else None
        if servicio is None or naturaleza is None:
            continue
        punta = "Comprador" if "puntacompradora" in producto else "Vendedor" if "puntavendedora" in producto else "Ambas" if servicio == "Compensación y liquidación" else None
        if punta is None:
            continue
        texto_rango = unicodedata.normalize("NFKD", modalidad).encode("ascii", "ignore").decode().lower()
        minimo, maximo = 0.0, float("inf")
        if servicio == "Registro de operación" and punta == "Comprador":
            # Los cuatro tramos del PT CUB son explícitos. Esta lectura evita inferir
            # equivocadamente la unidad de 500.000 cuando el segundo límite es 1 billón.
            if "200.000" in texto_rango and "500.000" in texto_rango:
                minimo, maximo = 200_000_000_000, 500_000_000_000
            elif "500.000" in texto_rango and "1 bill" in texto_rango:
                minimo, maximo = 500_000_000_000, 1_000_000_000_000
            elif "1 bill" in texto_rango and ">" in texto_rango:
                minimo, maximo = 1_000_000_000_000, float("inf")
            elif "200.000" in texto_rango:
                minimo, maximo = 0, 200_000_000_000
            else:
                raise ValueError(f"No se pudo interpretar el rango tarifario: {modalidad}")
        filas.append({
            "servicio": servicio, "naturaleza": naturaleza, "punta": punta, "minimo": minimo, "maximo": maximo,
            "tarifa": porcentaje(fila[columnas["tarifa"]]), "modalidad_cub": modalidad,
            "articulo_cub": fila[columnas["articulocub"]], "pagina_cub": fila[columnas["paginapdf"]],
        })
    tarifas = pd.DataFrame(filas)
    if tarifas.empty:
        raise ValueError("No se encontraron tarifas de registro MCP en el Inventario.")
    return tarifas


def preparar_originales(operaciones: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mcp = operaciones.loc[operaciones["naturaleza"].notna()].copy()
    descartadas = operaciones.loc[operaciones["negocio"].isin(EXCLUIDOS)].copy()
    no_mcp = operaciones.loc[~operaciones["negocio"].isin(set(MCP_CODIGOS) | EXCLUIDOS)].copy()
    descartadas = pd.concat([descartadas, no_mcp], ignore_index=True)
    inconsistentes = []
    validas = []
    for op, grupo in mcp.groupby("operacion", dropna=False):
        firma = grupo[CRITICOS_ORIGINAL].astype(str).drop_duplicates()
        if len(firma) > 1:
            temp = grupo.copy(); temp["motivo_alerta"] = "Operación original con información inconsistente entre archivos"
            inconsistentes.append(temp)
        else:
            validas.append(grupo.iloc[[0]])
    originales = pd.concat(validas, ignore_index=True) if validas else mcp.iloc[0:0].copy()
    alertas = pd.concat(inconsistentes, ignore_index=True) if inconsistentes else mcp.iloc[0:0].copy()
    return originales, pd.concat([descartadas, alertas], ignore_index=True)


def clasificar_adiciones(adiciones: pd.DataFrame, originales: pd.DataFrame) -> pd.DataFrame:
    lookup = originales.set_index("operacion")
    resultado = adiciones.copy()
    for campo in ["negocio", "naturaleza", "fecha_entrega_original", "fecha_operacion", "mandante_compra", "archivo_operacion"]:
        resultado[f"original_{campo}"] = resultado["operacion"].map(lookup[campo])
    resultado["dias_diferencia_entrega"] = (resultado["fecha_entrega_adicion"] - resultado["original_fecha_entrega_original"]).dt.days
    resultado["estado_clasificacion"] = "Clasificada"
    resultado["regla_aplicada"] = ""
    resultado["naturaleza"] = pd.NA
    no_original = resultado["original_naturaleza"].isna()
    resultado.loc[no_original, ["estado_clasificacion", "regla_aplicada"]] = ["No evaluable", "Operación original no encontrada o inconsistente"]
    forward = resultado["original_naturaleza"].eq("Forward")
    resultado.loc[forward, ["naturaleza", "regla_aplicada"]] = ["Forward", "Original Forward: adición Forward"]
    disponible = resultado["original_naturaleza"].eq("Disponible")
    sin_fecha = disponible & resultado["dias_diferencia_entrega"].isna()
    resultado.loc[sin_fecha, ["estado_clasificacion", "regla_aplicada"]] = ["No evaluable", "Fecha de entrega original o de adición no disponible"]
    anterior = disponible & resultado["dias_diferencia_entrega"].lt(0)
    resultado.loc[anterior, ["estado_clasificacion", "regla_aplicada"]] = ["No evaluable", "Entrega de adición anterior a entrega original"]
    hasta_30 = disponible & resultado["dias_diferencia_entrega"].between(0, 30, inclusive="both")
    resultado.loc[hasta_30, ["naturaleza", "regla_aplicada"]] = ["Disponible", "Original Disponible: entrega igual o hasta 30 días posterior"]
    mas_30 = disponible & resultado["dias_diferencia_entrega"].gt(30)
    resultado.loc[mas_30, ["naturaleza", "regla_aplicada"]] = ["Forward", "Original Disponible: entrega más de 30 días posterior"]
    resultado["mandante_compra"] = resultado["original_mandante_compra"]
    # El acumulado tarifario es anual (enero a diciembre) y se determina por
    # la fecha del evento que genera el cobro. Para una adición, esa fecha es
    # la solicitud de la adición, no la fecha de su operación original.
    resultado["anio_acumulado"] = resultado["fecha_solicitud"].dt.year
    resultado["fecha_evento"] = resultado["fecha_solicitud"]
    resultado["tipo_registro"] = "Adición"
    resultado["archivo_operacion"] = resultado["original_archivo_operacion"]
    return resultado


def tarifa_para(tarifas: pd.DataFrame, servicio: str, naturaleza: str, punta: str, acumulado_previo: float) -> pd.Series | None:
    t = tarifas.loc[(tarifas["servicio"] == servicio) & (tarifas["naturaleza"] == naturaleza)]
    if servicio == "Registro de operación":
        t = t.loc[t["punta"] == punta]
    else:
        t = t.loc[t["punta"].isin([punta, "Ambas"])]
    if t.empty:
        return None
    if servicio == "Compensación y liquidación" or punta == "Vendedor":
        return t.iloc[0]
    # Rango inferior aplica al cruzar el umbral: <= máximo; mínimo es estricto para los demás rangos.
    candidato = t.loc[(acumulado_previo > t["minimo"]) & (acumulado_previo <= t["maximo"])]
    if acumulado_previo == 0:
        candidato = t.loc[t["minimo"].eq(0)]
    return candidato.iloc[0] if not candidato.empty else None


def recalcular(eventos: pd.DataFrame, tarifas: pd.DataFrame, tolerancia: float) -> pd.DataFrame:
    datos = eventos.copy()
    datos["acumulado_previo"] = float("nan")
    datos["tarifa_compra_esperada"] = float("nan")
    datos["tarifa_venta_esperada"] = float("nan")
    datos["registro_compra_esperado"] = float("nan")
    datos["registro_venta_esperado"] = float("nan")
    datos["tarifa_cyl_compra_esperada"] = float("nan")
    datos["tarifa_cyl_venta_esperada"] = float("nan")
    datos["cyl_compra_esperado"] = float("nan")
    datos["cyl_venta_esperado"] = float("nan")
    datos["articulo_cub"] = ""
    datos["pagina_cub"] = ""
    evaluables = datos["naturaleza"].notna() & datos["mandante_compra"].notna() & datos["mandante_compra"].ne("") & datos["anio_acumulado"].notna()
    for _, indices in datos.loc[evaluables].groupby(["mandante_compra", "anio_acumulado", "naturaleza"], dropna=False).groups.items():
        grupo = datos.loc[list(indices)].sort_values(["fecha_evento", "operacion", "no_adicion"], na_position="last")
        acumulado = 0.0
        for indice, fila in grupo.iterrows():
            datos.at[indice, "acumulado_previo"] = acumulado
            compra = tarifa_para(tarifas, "Registro de operación", fila["naturaleza"], "Comprador", acumulado)
            venta = tarifa_para(tarifas, "Registro de operación", fila["naturaleza"], "Vendedor", acumulado)
            if compra is not None:
                datos.at[indice, "tarifa_compra_esperada"] = compra["tarifa"]
                datos.at[indice, "registro_compra_esperado"] = fila["valor_base"] * compra["tarifa"]
                datos.at[indice, "articulo_cub"] = texto_trazabilidad(compra["articulo_cub"])
                datos.at[indice, "pagina_cub"] = texto_trazabilidad(compra["pagina_cub"])
            if venta is not None:
                datos.at[indice, "tarifa_venta_esperada"] = venta["tarifa"]
                datos.at[indice, "registro_venta_esperado"] = fila["valor_base"] * venta["tarifa"]
            acumulado += 0 if pd.isna(fila["valor_base"]) else float(fila["valor_base"])
    for indice, fila in datos.loc[datos["naturaleza"].notna()].iterrows():
        compra_cyl = tarifa_para(tarifas, "Compensación y liquidación", fila["naturaleza"], "Comprador", 0)
        venta_cyl = tarifa_para(tarifas, "Compensación y liquidación", fila["naturaleza"], "Vendedor", 0)
        if compra_cyl is not None:
            datos.at[indice, "tarifa_cyl_compra_esperada"] = compra_cyl["tarifa"]
            datos.at[indice, "cyl_compra_esperado"] = fila["valor_base"] * compra_cyl["tarifa"]
        if venta_cyl is not None:
            datos.at[indice, "tarifa_cyl_venta_esperada"] = venta_cyl["tarifa"]
            datos.at[indice, "cyl_venta_esperado"] = fila["valor_base"] * venta_cyl["tarifa"]
    datos["diferencia_compra"] = datos["registro_compra_aplicado"] - datos["registro_compra_esperado"]
    datos["diferencia_venta"] = datos["registro_venta_aplicado"] - datos["registro_venta_esperado"]
    datos["diferencia_cyl_compra"] = datos["cyl_compra_aplicado"] - datos["cyl_compra_esperado"]
    datos["diferencia_cyl_venta"] = datos["cyl_venta_aplicado"] - datos["cyl_venta_esperado"]
    clasificacion_no_evaluable = datos["naturaleza"].isna() | (datos["tipo_registro"].eq("Adición") & datos["estado_clasificacion"].ne("Clasificada"))

    def evaluar(nombre: str, aplicado: str, esperado: str, diferencia: str, descripcion: str) -> None:
        estado = f"resultado_{nombre}"
        motivo = f"motivo_{nombre}"
        no_evaluable = clasificacion_no_evaluable | datos[aplicado].isna() | datos[esperado].isna()
        alerta = datos[diferencia].abs().gt(tolerancia) & ~no_evaluable
        datos[estado] = "Conforme"
        datos[motivo] = ""
        datos.loc[no_evaluable, estado] = "No evaluable"
        datos.loc[no_evaluable, motivo] = "No fue posible obtener todos los elementos del cálculo"
        sin_clasificar = no_evaluable & datos["tipo_registro"].eq("Adición") & datos["estado_clasificacion"].ne("Clasificada")
        if sin_clasificar.any():
            datos.loc[sin_clasificar, motivo] = datos.loc[sin_clasificar, "regla_aplicada"]
        datos.loc[alerta, estado] = "Alerta"
        datos.loc[alerta, motivo] = f"Diferencia en {descripcion} superior a tolerancia"

    evaluar("registro_compra", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "registro de operación - punta compradora")
    evaluar("registro_venta", "registro_venta_aplicado", "registro_venta_esperado", "diferencia_venta", "registro de operación - punta vendedora")
    evaluar("cyl_compra", "cyl_compra_aplicado", "cyl_compra_esperado", "diferencia_cyl_compra", "compensación y liquidación - punta compradora")
    evaluar("cyl_venta", "cyl_venta_aplicado", "cyl_venta_esperado", "diferencia_cyl_venta", "compensación y liquidación - punta vendedora")
    datos["resultado_cyl"] = "Conforme"
    datos.loc[datos[["resultado_cyl_compra", "resultado_cyl_venta"]].eq("Alerta").any(axis=1), "resultado_cyl"] = "Alerta"
    # Una punta pendiente no puede producir una conclusión de conformidad conjunta.
    parcial_cyl = datos[["resultado_cyl_compra", "resultado_cyl_venta"]].eq("No evaluable").any(axis=1)
    datos.loc[parcial_cyl & datos["resultado_cyl"].ne("Alerta"), "resultado_cyl"] = "No evaluable"
    datos["diferencia_cyl"] = datos[["diferencia_cyl_compra", "diferencia_cyl_venta"]].sum(axis=1, min_count=1)
    estados = ["resultado_registro_compra", "resultado_registro_venta", "resultado_cyl_compra", "resultado_cyl_venta"]
    datos["resultado"] = "Conforme"
    datos.loc[datos[estados].eq("Alerta").any(axis=1), "resultado"] = "Alerta"
    datos.loc[datos[estados].eq("No evaluable").all(axis=1), "resultado"] = "No evaluable"
    datos["motivo_alerta"] = ""
    return datos


def tabla(df: pd.DataFrame, columnas: list[str]) -> str:
    vista = df[[c for c in columnas if c in df]].copy()
    for c in vista.columns:
        if c.startswith("fecha_") or c.startswith("original_fecha"):
            vista[c] = pd.to_datetime(vista[c], errors="coerce").dt.strftime("%d/%m/%Y")
        if c.startswith("valor") or c.startswith("registro") or c.startswith("diferencia") or c == "acumulado_previo":
            vista[c] = vista[c].map(money)
        if c.startswith("tarifa"):
            vista[c] = vista[c].map(pct)
    return vista.fillna("No suministrado").to_html(index=False, escape=True, classes="data-table", border=0)


def html_reporte(ruta: Path, evaluados: pd.DataFrame, config: dict, fuentes: list[Path], segundos_ejecucion: float) -> dict:
    alertas = evaluados.loc[evaluados["resultado"].eq("Alerta")].copy()
    no_eval = evaluados.loc[evaluados["resultado"].eq("No evaluable")].copy()
    operaciones = evaluados.loc[evaluados["tipo_registro"].eq("Operación")]
    adiciones = evaluados.loc[evaluados["tipo_registro"].eq("Adición")]
    total = len(evaluados)
    por_alerta = len(alertas) / total if total else 0
    exceso_compra = alertas["diferencia_compra"].clip(lower=0).sum()
    exceso_venta = alertas["diferencia_venta"].clip(lower=0).sum()
    conclusion = ("No se identificaron diferencias superiores a la tolerancia en los registros evaluados."
                  if alertas.empty else
                  f"Se identificaron {len(alertas):,} alertas ({por_alerta:.1%}) que requieren análisis por operación, adición y punta.")
    columnas_operaciones = [
        "operacion", "negocio", "naturaleza", "mandante_compra", "fecha_operacion", "fecha_entrega_original",
        "acumulado_previo", "valor_base", "tarifa_compra_aplicada", "tarifa_compra_esperada",
        "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "tarifa_venta_aplicada",
        "tarifa_venta_esperada", "registro_venta_aplicado", "registro_venta_esperado", "diferencia_venta",
        "resultado", "motivo_alerta", "archivo_operacion",
    ]
    columnas_adiciones = [
        "operacion", "no_adicion", "naturaleza", "original_naturaleza", "mandante_compra", "fecha_solicitud",
        "fecha_entrega_adicion", "original_fecha_entrega_original", "dias_diferencia_entrega", "regla_aplicada",
        "acumulado_previo", "valor_base", "tarifa_compra_aplicada", "tarifa_compra_esperada",
        "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "tarifa_venta_aplicada",
        "tarifa_venta_esperada", "registro_venta_aplicado", "registro_venta_esperado", "diferencia_venta",
        "resultado", "motivo_alerta", "archivo_operacion", "archivo_adicion",
    ]
    alertas_operaciones = alertas.loc[alertas["tipo_registro"].eq("Operación")]
    alertas_adiciones = alertas.loc[alertas["tipo_registro"].eq("Adición")]
    no_eval_operaciones = no_eval.loc[no_eval["tipo_registro"].eq("Operación")]
    no_eval_adiciones = no_eval.loc[no_eval["tipo_registro"].eq("Adición")]
    detalle_alertas_operaciones = tabla(alertas_operaciones, columnas_operaciones) if not alertas_operaciones.empty else "<p>No se generaron alertas en operaciones.</p>"
    detalle_alertas_adiciones = tabla(alertas_adiciones, columnas_adiciones) if not alertas_adiciones.empty else "<p>No se generaron alertas en adiciones.</p>"
    detalle_no_eval_operaciones = tabla(no_eval_operaciones, columnas_operaciones) if not no_eval_operaciones.empty else "<p>No hay operaciones no evaluables.</p>"
    detalle_no_eval_adiciones = tabla(no_eval_adiciones, columnas_adiciones) if not no_eval_adiciones.empty else "<p>No hay adiciones no evaluables.</p>"
    resumen_naturaleza = evaluados.groupby(["tipo_registro", "naturaleza"], dropna=False).size().reset_index(name="Registros")
    resumen_html = tabla(resumen_naturaleza, ["tipo_registro", "naturaleza", "Registros"])
    fuentes_html = "".join(f"<li>{html.escape(p.name)}</li>" for p in fuentes)
    documento = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Indicador 01 · Tarifas MCP</title>
<style>:root{{--navy:#14395b;--blue:#1677b8;--red:#b42318;--green:#2f6b2f;--bg:#f4f7fb;--border:#d9e2ec;--muted:#667085}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font:14px Arial;color:#1f2937}}main{{max-width:1500px;margin:auto;padding:22px}}h1,h2,h3{{color:var(--navy)}}header{{border-bottom:3px solid var(--blue);padding-bottom:16px}}.muted{{color:var(--muted)}}nav{{margin:15px 0;display:flex;gap:8px;flex-wrap:wrap}}nav a{{background:#fff;border:1px solid var(--border);border-radius:16px;padding:6px 11px;color:var(--navy);text-decoration:none}}.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}}.kpi,.card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;margin-top:16px;box-shadow:0 2px 8px #0000000a}}.label{{color:var(--muted);font-size:12px}}.value{{font-size:24px;color:var(--navy);font-weight:bold;margin-top:5px}}.red{{color:var(--red)}}.green{{color:var(--green)}}.table-wrap{{max-height:560px;overflow:auto}}.data-table{{border-collapse:collapse;width:100%;font-size:12px}}.data-table th{{position:sticky;top:0;background:var(--navy);color:#fff;text-align:left;padding:8px;white-space:nowrap}}.data-table td{{padding:7px;border-bottom:1px solid var(--border);white-space:nowrap}}.data-table tr:nth-child(even){{background:#f8fafc}}@media(max-width:1000px){{.kpis{{grid-template-columns:repeat(3,1fr)}}}}@media(max-width:600px){{.kpis{{grid-template-columns:repeat(2,1fr)}}main{{padding:12px}}}}@media print{{@page{{size:A3 landscape;margin:10mm}}body{{background:#fff;font-size:9px}}main{{max-width:none;padding:0}}nav{{display:none}}.card,.kpi{{box-shadow:none;break-inside:avoid}}.table-wrap{{max-height:none;overflow:visible}}.data-table{{font-size:7px;table-layout:auto}}.data-table th{{position:static;white-space:normal;padding:4px}}.data-table td{{white-space:normal;overflow-wrap:anywhere;padding:3px}}}}</style></head>
<body><main><header><h1>Indicador 01 · Validación de tarifas de registro MCP</h1><p class="muted">Período evaluado: {html.escape(config['periodo_evaluado'])} · Ejecutado: {datetime.now():%d/%m/%Y %H:%M}</p></header>
<nav><a href="#resumen">Resumen</a><a href="#alertas">Alertas</a><a href="#noeval">No evaluables</a><a href="#operaciones">Operaciones</a><a href="#adiciones">Adiciones</a></nav>
<section id="resumen"><div class="kpis"><div class="kpi"><div class="label">Registros evaluados</div><div class="value">{total:,}</div></div><div class="kpi"><div class="label">Operaciones del período</div><div class="value">{len(operaciones):,}</div></div><div class="kpi"><div class="label">Adiciones del período</div><div class="value">{len(adiciones):,}</div></div><div class="kpi"><div class="label">Alertas</div><div class="value red">{len(alertas):,}</div></div><div class="kpi"><div class="label">Exceso compra</div><div class="value">{money(exceso_compra)}</div></div><div class="kpi"><div class="label">Exceso venta</div><div class="value">{money(exceso_venta)}</div></div></div></section>
<section class="card"><h2>Conclusión</h2><p>{html.escape(conclusion)}</p><p class="muted">Las alertas son indicios para revisión. Las diferencias se comparan sin IVA y con tolerancia de {money(config['tolerancia_cop'])} por punta.</p></section>
<section class="card"><h2>Resumen por población y naturaleza</h2><div class="table-wrap">{resumen_html}</div></section>
<section id="alertas" class="card"><h2>Alertas</h2><h3>Operaciones</h3><div class="table-wrap">{detalle_alertas_operaciones}</div><h3>Adiciones</h3><div class="table-wrap">{detalle_alertas_adiciones}</div></section>
<section id="noeval" class="card"><h2>Registros no evaluables</h2><h3>Operaciones</h3><div class="table-wrap">{detalle_no_eval_operaciones}</div><h3>Adiciones</h3><div class="table-wrap">{detalle_no_eval_adiciones}</div></section>
<section id="operaciones" class="card"><h2>Operaciones del período</h2><p class="muted">La tarifa aplicada se calcula como el registro efectivamente cobrado dividido entre el valor de la operación.</p><div class="table-wrap">{tabla(operaciones, columnas_operaciones)}</div></section>
<section id="adiciones" class="card"><h2>Adiciones del período</h2><p class="muted">La tarifa aplicada se calcula como el registro efectivamente cobrado dividido entre el valor de la adición. Se conserva el detalle de la operación original solo para sustentar su clasificación.</p><div class="table-wrap">{tabla(adiciones, columnas_adiciones)}</div></section>
<section class="card"><h2>Fuentes utilizadas</h2><ul>{fuentes_html}</ul></section></main></body></html>'''
    ruta.write_text(documento, encoding="utf-8")
    return {"indicator_id": "ING-01", "version": VERSION, "period": config["periodo_evaluado"], "generated_at": datetime.now().isoformat(timespec="seconds"), "execution_seconds": round(segundos_ejecucion, 2), "conclusion": conclusion, "metrics": {"evaluated": total, "operations": len(operaciones), "additions": len(adiciones), "alerts": len(alertas), "not_evaluable": len(no_eval), "alert_rate": round(por_alerta, 6), "excess_purchase": round(float(exceso_compra), 2), "excess_sale": round(float(exceso_venta), 2)}}


def vista_indicador(titulo: str, poblacion: pd.DataFrame, estado: str, diferencia: str, columnas: list[str], serie: list[dict] | None = None, activo: bool = False) -> tuple[str, dict]:
    """Construye una vista independiente y sus métricas normalizadas."""
    alertas = poblacion.loc[poblacion[estado].eq("Alerta")]
    no_evaluables = poblacion.loc[poblacion[estado].eq("No evaluable")]
    detalle = tabla(poblacion, columnas) if not poblacion.empty else "<p>No hay registros para este período.</p>"
    detalle_alertas = tabla(alertas, columnas) if not alertas.empty else "<p>No se identificaron tarifas mal aplicadas.</p>"
    detalle_no_evaluables = tabla(no_evaluables, columnas) if not no_evaluables.empty else "<p>No hay registros no evaluables.</p>"
    diferencia_total = float(alertas[diferencia].sum()) if not alertas.empty else 0.0
    resumen_total = f'<p class="total-alertas"><strong>Total del detalle: {money(diferencia_total)}</strong> · {len(alertas)} registros con alerta.</p>' if not alertas.empty else ""
    if poblacion.empty:
        detalle_alertas = "<p>Sin población en las fuentes para este período.</p>"
    mini_alertas = mini_grafica(serie or [], "Tarifas mal aplicadas", lambda v: str(int(v)))
    mini_diferencia = mini_grafica(serie or [], "_diferencia_neta", money)
    identificador = normalizar(titulo)
    html_vista = f'''<section id="{identificador}" class="tab-panel{' active' if activo else ''}"><div class="card"><h2>{html.escape(titulo)}</h2>
<div class="kpis"><div class="kpi"><div class="label">Población</div><div class="value">{len(poblacion):,}</div></div><div class="kpi"><div class="label">Tarifas mal aplicadas</div><div class="value red">{len(alertas):,}</div>{mini_alertas}</div><div class="kpi"><div class="label">No evaluables</div><div class="value">{len(no_evaluables):,}</div></div><div class="kpi"><div class="label">Diferencia neta alertas</div><div class="value">{money(diferencia_total)}</div>{mini_diferencia}</div></div>
<h3>Detalle de tarifas mal aplicadas</h3><div class="table-wrap">{detalle_alertas}</div>{resumen_total}
<h3>Registros no evaluables</h3><div class="table-wrap">{detalle_no_evaluables}</div>
<h3>Detalle de cálculo de la población</h3><div class="table-wrap">{detalle}</div></div></section>'''
    metricas = {"population": len(poblacion), "alerts": len(alertas), "not_evaluable": len(no_evaluables), "alert_difference_net": round(diferencia_total, 2), "data_available": not poblacion.empty}
    return html_vista, metricas


def cargar_comparativo_tres_meses(resultados: Path, periodo_actual: str, metricas_actuales: dict) -> dict[str, list[dict]]:
    """Recupera el mes evaluado y los dos meses calendario anteriores.

    Solo utiliza los resultado.json con las cinco métricas normalizadas. Una
    repetición de un mismo mes sustituye la corrida anterior de ese período en
    el comparativo, pero no altera los resultados históricos almacenados.
    """
    corridas: dict[str, dict] = {}
    for ruta in resultados.glob("*/resultado.json"):
        try:
            contenido = json.loads(ruta.read_text(encoding="utf-8"))
            periodo = str(contenido.get("period", ""))
            if not re.fullmatch(r"\d{4}-\d{2}", periodo) or not contenido.get("indicators"):
                continue
            pd.Period(periodo, freq="M")
            anterior = corridas.get(periodo)
            if anterior is None or str(contenido.get("generated_at", "")) > str(anterior.get("generated_at", "")):
                corridas[periodo] = contenido
        except (OSError, ValueError, TypeError, AttributeError):
            continue

    # La corrida actual prevalece incluso si ya existía un resultado de ese mes.
    corridas[periodo_actual] = {"period": periodo_actual, "indicators": metricas_actuales}
    periodo_limite = pd.Period(periodo_actual, freq="M")
    periodos = [str(periodo_limite - n) for n in (2, 1, 0)]

    series: dict[str, list[dict]] = {}
    for indicador in metricas_actuales:
        filas = []
        anterior_alertas = None
        for periodo in periodos:
            metricas = corridas.get(periodo, {}).get("indicators", {}).get(indicador)
            if not isinstance(metricas, dict) or not metricas.get("data_available", metricas.get("population", 0) > 0):
                filas.append({"Período": periodo, "_disponible": False, "Tarifas mal aplicadas": None, "_diferencia_neta": None, "Tendencia de alertas": "Sin información"})
                anterior_alertas = None
                continue
            alertas = int(metricas.get("alerts", 0))
            if anterior_alertas is None:
                tendencia = "Sin período anterior comparable"
            elif alertas > anterior_alertas:
                tendencia = f"Aumenta (+{alertas - anterior_alertas})"
            elif alertas < anterior_alertas:
                tendencia = f"Disminuye ({alertas - anterior_alertas})"
            else:
                tendencia = "Se mantiene (0)"
            filas.append({
                "Período": periodo,
                "_disponible": True,
                "Población": int(metricas.get("population", 0)),
                "Tarifas mal aplicadas": alertas,
                "No evaluables": int(metricas.get("not_evaluable", 0)),
                "Diferencia neta de alertas": money(metricas.get("alert_difference_net", 0)),
                "_diferencia_neta": float(metricas.get("alert_difference_net", 0)),
                "Tendencia de alertas": tendencia,
            })
            anterior_alertas = alertas
        series[indicador] = filas
    return series


def mini_grafica(filas: list[dict], clave: str, formato) -> str:
    """SVG compacto con cero real, datos faltantes y diferencias negativas."""
    disponibles = [float(f[clave]) for f in filas if f.get("_disponible", True) and f.get(clave) is not None]
    lo = min([0.0] + disponibles)
    hi = max([0.0] + disponibles)
    if hi == lo:
        hi = lo + 1
    arriba, abajo = 16, 48
    def y(v):
        return abajo - (v - lo) * (abajo - arriba) / (hi - lo)
    cero = y(0)
    colores = ["#8da4b9", "#426c8f", "#14395b"]
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    barras = []
    for i, fila in enumerate(filas):
        x = 22 + i * 61
        periodo = fila["Período"]
        etiqueta = f'{meses[int(periodo[-2:]) - 1]} {periodo[2:4]}'
        disponible = fila.get("_disponible", True) and fila.get(clave) is not None
        valor = float(fila[clave]) if disponible else None
        texto = formato(valor) if disponible else "Sin información"
        if disponible:
            if valor == 0:
                dibujo = f'<line x1="{x}" y1="{cero:.1f}" x2="{x + 27}" y2="{cero:.1f}" stroke="{colores[i]}" stroke-width="2"/>'
            else:
                dibujo = f'<rect x="{x}" y="{min(cero,y(valor)):.1f}" width="27" height="{abs(cero-y(valor)):.1f}" rx="2" fill="{colores[i]}"/>'
        else:
            dibujo = f'<text x="{x + 14}" y="34" text-anchor="middle" class="spark-label">s/d</text>'
        barras.append(f'<g><title>{html.escape(periodo)}: {html.escape(texto)}</title>{dibujo}<text x="{x + 14}" y="63" text-anchor="middle" class="spark-label">{etiqueta}</text></g>')
    ultimo = filas[-1] if filas else {}
    if clave == "Tarifas mal aplicadas":
        leyenda = ultimo.get("Tendencia de alertas", "Sin información")
    elif len(filas) >= 2 and all(f.get("_disponible", True) and f.get(clave) is not None for f in filas[-2:]):
        delta = filas[-1][clave] - filas[-2][clave]
        leyenda = ("Aumenta " if delta > 0 else "Disminuye " if delta < 0 else "Se mantiene ") + (money(abs(delta)) if delta else "(0)")
    else:
        leyenda = "Sin mes anterior comparable"
    accesible = "; ".join(f'{f["Período"]}: {formato(f[clave]) if f.get("_disponible",True) and f.get(clave) is not None else "Sin información"}' for f in filas)
    return f'<svg class="mini-chart" viewBox="0 0 210 68" role="img" aria-label="{html.escape(accesible, quote=True)}"><line x1="12" y1="{cero:.1f}" x2="202" y2="{cero:.1f}" stroke="#ccd5df"/>{"".join(barras)}</svg><div class="spark-caption">{html.escape(leyenda)}</div>'


def grafico_comparativo(series: dict[str, list[dict]], clave: str, titulo: str, formato) -> str:
    """Genera un gráfico SVG de barras agrupadas, sin dependencias externas."""
    indicadores = list(series)
    periodos = sorted({fila["Período"] for filas in series.values() for fila in filas})
    if not indicadores or not periodos:
        return "<p>No hay información suficiente para construir la gráfica.</p>"
    valores = {
        indicador: {fila["Período"]: float(fila.get(clave, 0) or 0) for fila in filas}
        for indicador, filas in series.items()
    }
    todos = [valor for indicador in indicadores for valor in valores[indicador].values()] or [0]
    minimo, maximo = min(0.0, min(todos)), max(0.0, max(todos))
    if minimo == maximo:
        maximo = minimo + 1
    ancho, alto, margen_izq, margen_der, margen_sup, margen_inf = 1160, 360, 70, 30, 38, 75
    area_ancho, area_alto = ancho - margen_izq - margen_der, alto - margen_sup - margen_inf
    escala = area_alto / (maximo - minimo)
    y_cero = margen_sup + (maximo * escala)
    colores = ["#1677b8", "#48a9a6", "#7c5cc4"]
    grupo = area_ancho / len(indicadores)
    ancho_barra = min(34, (grupo * 0.7) / max(1, len(periodos)))
    barras, etiquetas = [], []
    for indice_indicador, indicador in enumerate(indicadores):
        centro = margen_izq + grupo * (indice_indicador + 0.5)
        etiquetas.append(f'<text x="{centro:.1f}" y="{alto - 30}" text-anchor="middle" class="svg-label">{html.escape(indicador)}</text>')
        inicio = centro - (ancho_barra * len(periodos)) / 2
        for indice_periodo, periodo in enumerate(periodos):
            valor = valores[indicador].get(periodo, 0.0)
            y_valor = margen_sup + (maximo - valor) * escala
            y = min(y_cero, y_valor)
            altura = max(1, abs(y_cero - y_valor))
            x = inicio + indice_periodo * ancho_barra
            barras.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(2, ancho_barra - 3):.1f}" height="{altura:.1f}" fill="{colores[indice_periodo % len(colores)]}"><title>{html.escape(indicador)} · {html.escape(periodo)}: {html.escape(formato(valor))}</title></rect>'
            )
    leyenda = "".join(
        f'<span class="chart-legend"><i style="background:{colores[indice % len(colores)]}"></i>{html.escape(periodo)}</span>'
        for indice, periodo in enumerate(periodos)
    )
    return f'''<div class="chart-card"><h3>{html.escape(titulo)}</h3><div class="legend">{leyenda}</div>
<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{html.escape(titulo)}" class="trend-chart">
<line x1="{margen_izq}" y1="{y_cero:.1f}" x2="{ancho - margen_der}" y2="{y_cero:.1f}" class="axis"/>
<text x="{margen_izq - 8}" y="{margen_sup + 5}" text-anchor="end" class="svg-label">{html.escape(formato(maximo))}</text>
<text x="{margen_izq - 8}" y="{alto - margen_inf + 5}" text-anchor="end" class="svg-label">{html.escape(formato(minimo))}</text>
{''.join(barras)}{''.join(etiquetas)}</svg></div>'''


def panel_comparativo_tres_meses(series: dict[str, list[dict]], titulos: dict[str, str]) -> str:
    paneles = []
    for indicador, titulo in titulos.items():
        filas = series.get(indicador, [])
        if not filas:
            detalle = "<p>No hay resultados comparables disponibles.</p>"
        else:
            detalle = pd.DataFrame(filas).drop(columns=["_diferencia_neta"], errors="ignore").to_html(index=False, escape=True, classes="data-table", border=0)
        paneles.append(f"<div class=\"card\"><h2>{html.escape(titulo)}</h2><div class=\"table-wrap\">{detalle}</div></div>")
    grafico_alertas = grafico_comparativo(series, "Tarifas mal aplicadas", "Tarifas mal aplicadas por indicador", lambda valor: f"{valor:,.0f}")
    grafico_diferencias = grafico_comparativo(series, "_diferencia_neta", "Diferencia neta de alertas por indicador", money)
    return "<section id=\"comparativo\" class=\"tab-panel active\"><div class=\"card\"><h2>Resumen comparativo de los últimos tres meses</h2><p class=\"muted\">La tendencia se determina por la variación en el número de tarifas mal aplicadas frente al período inmediatamente anterior. Se usa la última ejecución disponible de cada mes.</p>" + grafico_alertas + grafico_diferencias + "</div>" + "".join(paneles) + "</section>"


def obtener_vistas(evaluados: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame, str, str, list[str]]]:
    """Define una sola población para las cinco salidas: HTML, Excel y PDF."""
    columnas_operacion_registro = ["operacion", "negocio", "naturaleza", "mandante_compra", "fecha_operacion", "fecha_entrega_original", "acumulado_previo", "valor_base", "tarifa_compra_aplicada", "tarifa_compra_esperada", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "resultado_registro_compra", "motivo_registro_compra", "archivo_operacion"]
    columnas_operacion_venta = ["mandante_compra" if c == "mandante_venta" else c for c in [c.replace("compra", "venta") for c in columnas_operacion_registro]]
    columnas_cyl = ["tipo_registro", "operacion", "no_adicion", "negocio", "naturaleza", "mandante_compra", "fecha_evento", "valor_base", "tarifa_cyl_compra_aplicada", "tarifa_cyl_compra_esperada", "cyl_compra_aplicado", "cyl_compra_esperado", "diferencia_cyl_compra", "resultado_cyl_compra", "motivo_cyl_compra", "tarifa_cyl_venta_aplicada", "tarifa_cyl_venta_esperada", "cyl_venta_aplicado", "cyl_venta_esperado", "diferencia_cyl_venta", "resultado_cyl_venta", "motivo_cyl_venta"]
    columnas_adicion_registro = ["operacion", "no_adicion", "naturaleza", "original_naturaleza", "mandante_compra", "fecha_solicitud", "fecha_entrega_adicion", "original_fecha_entrega_original", "dias_diferencia_entrega", "regla_aplicada", "acumulado_previo", "valor_base", "tarifa_compra_aplicada", "tarifa_compra_esperada", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "resultado_registro_compra", "motivo_registro_compra", "archivo_operacion", "archivo_adicion"]
    columnas_adicion_venta = ["mandante_compra" if c == "mandante_venta" else c for c in [c.replace("compra", "venta") for c in columnas_adicion_registro]]
    operaciones = evaluados.loc[evaluados["tipo_registro"].eq("Operación")]
    adiciones = evaluados.loc[evaluados["tipo_registro"].eq("Adición")]
    return [
        ("IND-01", "Tarifas mal aplicadas - MCP Registro de operación - punta compradora", operaciones, "resultado_registro_compra", "diferencia_compra", columnas_operacion_registro),
        ("IND-02", "Tarifas mal aplicadas - MCP Registro de operación - punta vendedora", operaciones, "resultado_registro_venta", "diferencia_venta", columnas_operacion_venta),
        ("IND-03", "Tarifas mal aplicadas - MCP Servicio de compensación y liquidación", evaluados, "resultado_cyl", "diferencia_cyl", columnas_cyl),
        ("IND-04", "Tarifas mal aplicadas - MCP Registro de adición - punta compradora", adiciones, "resultado_registro_compra", "diferencia_compra", columnas_adicion_registro),
        ("IND-05", "Tarifas mal aplicadas - MCP Registro de adición - punta vendedora", adiciones, "resultado_registro_venta", "diferencia_venta", columnas_adicion_venta),
    ]


def valor_exportable(valor: object) -> object:
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    if pd.isna(valor):
        return None
    return valor.item() if hasattr(valor, "item") else valor


def es_monetario(campo: str) -> bool:
    return campo.startswith(("valor", "registro", "diferencia", "cyl_")) or campo == "acumulado_previo"


def agregar_tabla_excel(hoja, dataframe: pd.DataFrame, columnas: list[str], fila_inicio: int) -> int:
    """Escribe una tabla con formato institucional y devuelve la siguiente fila."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    columnas = [c for c in columnas if c in dataframe.columns]
    encabezado = fila_inicio
    for indice, campo in enumerate(columnas, 1):
        celda = hoja.cell(encabezado, indice, etiqueta_columna(campo))
        celda.fill = PatternFill("solid", fgColor="14395B")
        celda.font = Font(color="FFFFFF", bold=True)
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    borde = Border(bottom=Side(style="thin", color="D9E2EC"))
    for fila, (_, registro) in enumerate(dataframe[columnas].iterrows(), encabezado + 1):
        for indice, campo in enumerate(columnas, 1):
            celda = hoja.cell(fila, indice, valor_exportable(registro[campo]))
            celda.alignment = Alignment(vertical="top", wrap_text=campo.startswith(("motivo", "regla", "archivo")))
            celda.border = borde
            if es_monetario(campo):
                celda.number_format = '#,##0;[Red]-#,##0'
            elif campo.startswith("tarifa"):
                celda.number_format = '0.000%'
            elif campo.startswith("fecha_") or campo.startswith("original_fecha"):
                celda.number_format = 'dd/mm/yyyy'
    if columnas:
        hoja.auto_filter.ref = f"A{encabezado}:{chr(64 + min(len(columnas), 26))}{max(encabezado, encabezado + len(dataframe))}"
    return encabezado + len(dataframe) + 2


def exportar_excel(ruta: Path, evaluados: pd.DataFrame, config: dict, fuentes: list[Path], metricas: dict) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"
    azul = PatternFill("solid", fgColor="14395B")
    resumen["A1"] = "Indicador 01 - Validación de tarifas MCP"
    resumen["A1"].font = Font(color="FFFFFF", bold=True, size=14)
    resumen["A1"].fill = azul
    resumen.merge_cells("A1:E1")
    resumen["A2"] = "Período evaluado"; resumen["B2"] = config["periodo_evaluado"]
    resumen["A3"] = "Estado"; resumen["B3"] = "Información en proceso de validación"
    resumen["A4"] = "Tolerancia (COP)"; resumen["B4"] = config["tolerancia_cop"]; resumen["B4"].number_format = '#,##0'
    encabezados = ["Indicador", "Población", "Tarifas mal aplicadas", "No evaluables", "Diferencia neta alertas"]
    for c, etiqueta in enumerate(encabezados, 1):
        celda = resumen.cell(6, c, etiqueta); celda.fill = azul; celda.font = Font(color="FFFFFF", bold=True); celda.alignment = Alignment(horizontal="center", wrap_text=True)
    for fila, (codigo, valores) in enumerate(metricas.items(), 7):
        resumen.cell(fila, 1, codigo)
        resumen.cell(fila, 2, valores["population"])
        resumen.cell(fila, 3, valores["alerts"])
        resumen.cell(fila, 4, valores["not_evaluable"])
        resumen.cell(fila, 5, valores["alert_difference_net"]).number_format = '#,##0;[Red]-#,##0'
    resumen["A14"] = "Fuentes utilizadas"; resumen["A14"].font = Font(bold=True, color="FFFFFF"); resumen["A14"].fill = azul
    for fila, fuente in enumerate(fuentes, 15):
        resumen.cell(fila, 1, fuente.name)
    resumen.column_dimensions["A"].width = 34
    for columna in "BCDE": resumen.column_dimensions[columna].width = 24

    for codigo, titulo, poblacion, estado, diferencia, columnas in obtener_vistas(evaluados):
        hoja = libro.create_sheet(f"{codigo.replace('-', '_')}")
        hoja.sheet_properties.tabColor = "14395B"
        hoja["A1"] = titulo; hoja["A1"].font = Font(color="FFFFFF", bold=True, size=12); hoja["A1"].fill = azul
        hoja.merge_cells("A1:H1")
        alertas = poblacion.loc[poblacion[estado].eq("Alerta")]
        no_evaluables = poblacion.loc[poblacion[estado].eq("No evaluable")]
        fila = 3
        hoja.cell(fila, 1, "Población"); hoja.cell(fila, 2, len(poblacion))
        hoja.cell(fila, 3, "Tarifas mal aplicadas"); hoja.cell(fila, 4, len(alertas))
        hoja.cell(fila, 5, "No evaluables"); hoja.cell(fila, 6, len(no_evaluables))
        hoja.cell(fila, 7, "Diferencia neta alertas"); hoja.cell(fila, 8, float(alertas[diferencia].sum()) if not alertas.empty else 0).number_format = '#,##0;[Red]-#,##0'
        hoja.cell(5, 1, "Detalle de cálculo de la población").font = Font(bold=True, color="14395B")
        agregar_tabla_excel(hoja, poblacion, columnas, 6)
        for indice, campo in enumerate([c for c in columnas if c in poblacion.columns], 1):
            hoja.column_dimensions[chr(64 + min(indice, 26))].width = min(28, max(12, len(etiqueta_columna(campo)) + 2))
        hoja.freeze_panes = "A6"
    libro.save(ruta)


def celdas_pdf(dataframe: pd.DataFrame, columnas: list[str]) -> list[list[str]]:
    columnas = [c for c in columnas if c in dataframe.columns]
    resultado = [[etiqueta_columna(c) for c in columnas]]
    for _, fila in dataframe[columnas].iterrows():
        valores = []
        for campo in columnas:
            valor = fila[campo]
            if pd.isna(valor):
                valores.append("")
            elif campo.startswith("tarifa"):
                valores.append(pct(valor))
            elif es_monetario(campo):
                valores.append(money(valor))
            elif campo.startswith("fecha_") or campo.startswith("original_fecha"):
                valores.append(pd.to_datetime(valor).strftime("%d/%m/%Y"))
            else:
                valores.append(str(valor))
        resultado.append(valores)
    return resultado


def exportar_pdf(ruta: Path, evaluados: pd.DataFrame, config: dict, fuentes: list[Path]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("TituloMCP", parent=estilos["Heading1"], textColor=colors.HexColor("#14395B"), fontSize=15, spaceAfter=7)
    subtitulo = ParagraphStyle("SubtituloMCP", parent=estilos["BodyText"], textColor=colors.HexColor("#667085"), fontSize=8, spaceAfter=7)
    encabezado = ParagraphStyle("EncabezadoMCP", parent=estilos["BodyText"], textColor=colors.white, fontSize=4.5, leading=5, alignment=TA_CENTER)
    celda = ParagraphStyle("CeldaMCP", parent=estilos["BodyText"], fontSize=4.5, leading=5.5)
    doc = BaseDocTemplate(str(ruta), pagesize=landscape(A3), leftMargin=12*mm, rightMargin=12*mm, topMargin=13*mm, bottomMargin=13*mm)
    ancho, alto = landscape(A3)
    marco = Frame(doc.leftMargin, doc.bottomMargin, ancho-doc.leftMargin-doc.rightMargin, alto-doc.topMargin-doc.bottomMargin, id="normal")
    def pie(canvas, documento):
        canvas.saveState(); canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(doc.leftMargin, 7*mm, "Información en proceso de validación · Indicador 01 - Tarifas MCP")
        canvas.drawRightString(ancho-doc.rightMargin, 7*mm, f"Página {documento.page}"); canvas.restoreState()
    doc.addPageTemplates([PageTemplate(id="MCP", frames=[marco], onPage=pie)])
    historia = [Paragraph("Indicador 01 - Validación de tarifas MCP", titulo), Paragraph(f"Período evaluado: {config['periodo_evaluado']} · Tolerancia: {money(config['tolerancia_cop'])} · Generado: {datetime.now():%d/%m/%Y %H:%M}", subtitulo), Paragraph("Información en proceso de validación.", subtitulo)]
    for _, titulo_vista, poblacion, estado, diferencia, columnas in obtener_vistas(evaluados):
        alertas = poblacion.loc[poblacion[estado].eq("Alerta")]
        no_evaluables = poblacion.loc[poblacion[estado].eq("No evaluable")]
        historia += [Spacer(1, 3), Paragraph(titulo_vista, titulo)]
        resumen = [["Población", str(len(poblacion)), "Tarifas mal aplicadas", str(len(alertas)), "No evaluables", str(len(no_evaluables)), "Diferencia neta", money(float(alertas[diferencia].sum()) if not alertas.empty else 0)]]
        tabla_resumen = Table(resumen, colWidths=[22*mm, 15*mm, 30*mm, 15*mm, 24*mm, 15*mm, 25*mm, 30*mm])
        tabla_resumen.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F4F7FB")), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#D9E2EC")), ("FONT", (0,0), (-1,-1), "Helvetica", 6), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        historia.append(tabla_resumen)
        for encabezado_seccion, dataframe in [("Detalle de tarifas mal aplicadas", alertas), ("Registros no evaluables", no_evaluables), ("Detalle de cálculo de la población", poblacion)]:
            historia.append(Spacer(1, 4)); historia.append(Paragraph(encabezado_seccion, ParagraphStyle("Sec"+encabezado_seccion, parent=estilos["Heading3"], textColor=colors.HexColor("#14395B"), fontSize=8, spaceAfter=3)))
            if dataframe.empty:
                historia.append(Paragraph("Sin registros.", subtitulo)); continue
            datos_tabla = celdas_pdf(dataframe, columnas)
            datos_parrafo = [[Paragraph(html.escape(str(v)), encabezado if fila == 0 else celda) for v in fila_datos] for fila, fila_datos in enumerate(datos_tabla)]
            ancho_util = ancho-doc.leftMargin-doc.rightMargin
            tabla = Table(datos_parrafo, colWidths=[ancho_util/len(datos_parrafo[0])]*len(datos_parrafo[0]), repeatRows=1)
            tabla.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#14395B")), ("GRID", (0,0), (-1,-1), .2, colors.HexColor("#D9E2EC")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
            historia.append(tabla)
        historia.append(PageBreak())
    historia += [Paragraph("Fuentes utilizadas", titulo)] + [Paragraph(html.escape(f.name), subtitulo) for f in fuentes]
    doc.build(historia)


def html_reporte_v2(ruta: Path, evaluados: pd.DataFrame, config: dict, fuentes: list[Path], segundos_ejecucion: float, resultados: Path) -> dict:
    """Dashboard con cinco vistas independientes para los indicadores MCP."""
    columnas_operacion_registro = ["operacion", "negocio", "naturaleza", "mandante_compra", "fecha_operacion", "fecha_entrega_original", "acumulado_previo", "valor_base", "tarifa_compra_aplicada", "tarifa_compra_esperada", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "resultado_registro_compra", "motivo_registro_compra", "archivo_operacion"]
    columnas_operacion_venta = [c.replace("compra", "venta") for c in columnas_operacion_registro]
    columnas_operacion_venta = ["mandante_compra" if c == "mandante_venta" else c for c in columnas_operacion_venta]
    columnas_cyl = ["tipo_registro", "operacion", "no_adicion", "negocio", "naturaleza", "mandante_compra", "fecha_evento", "valor_base", "tarifa_cyl_compra_aplicada", "tarifa_cyl_compra_esperada", "cyl_compra_aplicado", "cyl_compra_esperado", "diferencia_cyl_compra", "resultado_cyl_compra", "motivo_cyl_compra", "tarifa_cyl_venta_aplicada", "tarifa_cyl_venta_esperada", "cyl_venta_aplicado", "cyl_venta_esperado", "diferencia_cyl_venta", "resultado_cyl_venta", "motivo_cyl_venta"]
    columnas_adicion_registro = ["operacion", "no_adicion", "naturaleza", "original_naturaleza", "mandante_compra", "fecha_solicitud", "fecha_entrega_adicion", "original_fecha_entrega_original", "dias_diferencia_entrega", "regla_aplicada", "acumulado_previo", "valor_base", "tarifa_compra_aplicada", "tarifa_compra_esperada", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra", "resultado_registro_compra", "motivo_registro_compra", "archivo_operacion", "archivo_adicion"]
    columnas_adicion_venta = [c.replace("compra", "venta") for c in columnas_adicion_registro]
    columnas_adicion_venta = ["mandante_compra" if c == "mandante_venta" else c for c in columnas_adicion_venta]

    operaciones = evaluados.loc[evaluados["tipo_registro"].eq("Operación")]
    adiciones = evaluados.loc[evaluados["tipo_registro"].eq("Adición")]
    vistas = [
        ("Tarifas mal aplicadas - MCP Registro de operación - punta compradora", operaciones, "resultado_registro_compra", "diferencia_compra", columnas_operacion_registro),
        ("Tarifas mal aplicadas - MCP Registro de operación - punta vendedora", operaciones, "resultado_registro_venta", "diferencia_venta", columnas_operacion_venta),
        ("Tarifas mal aplicadas - MCP Servicio de compensación y liquidación", evaluados, "resultado_cyl", "diferencia_cyl", columnas_cyl),
        ("Tarifas mal aplicadas - MCP Registro de adición - punta compradora", adiciones, "resultado_registro_compra", "diferencia_compra", columnas_adicion_registro),
        ("Tarifas mal aplicadas - MCP Registro de adición - punta vendedora", adiciones, "resultado_registro_venta", "diferencia_venta", columnas_adicion_venta),
    ]
    paneles, metricas, botones = [], {}, []
    for posicion, (titulo, poblacion, estado, diferencia, columnas) in enumerate(vistas):
        alertas = poblacion.loc[poblacion[estado].eq("Alerta")]
        resumen = {"population": len(poblacion), "alerts": len(alertas), "not_evaluable": int(poblacion[estado].eq("No evaluable").sum()), "alert_difference_net": round(float(alertas[diferencia].sum()), 2), "data_available": not poblacion.empty}
        identificador = normalizar(titulo)
        metricas[f"IND-0{posicion + 1}"] = resumen
        botones.append(f'<button class="tab-button{" active" if posicion == 0 else ""}" data-target="{identificador}">IND-0{posicion + 1}</button>')
    series = cargar_comparativo_tres_meses(resultados, config["periodo_evaluado"], metricas)
    for posicion, (titulo, poblacion, estado, diferencia, columnas) in enumerate(vistas):
        panel, _ = vista_indicador(titulo, poblacion, estado, diferencia, columnas, series[f"IND-0{posicion + 1}"], posicion == 0)
        paneles.append(panel)
    comparativo = ""
    fuentes_html = "".join(f"<li>{html.escape(p.name)}</li>" for p in fuentes)
    documento = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Indicador 01 · Tarifas MCP</title>
<style>:root{{--navy:#14395b;--blue:#1677b8;--red:#b42318;--bg:#f4f7fb;--border:#d9e2ec;--muted:#667085}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font:14px Arial;color:#1f2937}}main{{max-width:1600px;margin:auto;padding:22px}}h1,h2,h3{{color:var(--navy)}}header{{border-bottom:3px solid var(--blue);padding-bottom:16px}}.muted{{color:var(--muted)}}.toolbar{{margin:15px 0;display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}}nav{{display:flex;gap:8px;flex-wrap:wrap}}.tab-button{{background:#fff;border:1px solid var(--border);border-radius:16px;padding:7px 12px;color:var(--navy);cursor:pointer}}.tab-button.active{{background:var(--navy);color:#fff}}.export-actions{{display:flex;gap:8px;flex-wrap:wrap}}.export-button{{background:var(--navy);border:1px solid var(--navy);border-radius:16px;padding:7px 12px;color:#fff;text-decoration:none;font-weight:bold}}.export-button.excel{{background:#fff;color:var(--navy)}}.tab-panel{{display:none}}.tab-panel.active{{display:block}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.kpi,.card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;margin-top:16px;box-shadow:0 2px 8px #0000000a}}.label{{color:var(--muted);font-size:12px}}.value{{font-size:22px;color:var(--navy);font-weight:bold;margin-top:5px}}.red{{color:var(--red)}}.table-wrap{{max-height:560px;overflow:auto}}.data-table{{border-collapse:collapse;width:100%;font-size:12px}}.data-table th{{position:sticky;top:0;background:var(--navy);color:#fff;text-align:left;padding:8px;white-space:nowrap}}.data-table td{{padding:7px;border-bottom:1px solid var(--border);white-space:nowrap}}.data-table tr:nth-child(even){{background:#f8fafc}}.chart-card{{margin-top:18px;padding:14px;border:1px solid var(--border);border-radius:10px;background:#fbfdff}}.chart-card h3{{margin:0 0 6px}}.trend-chart{{display:block;width:100%;height:auto}}.axis{{stroke:#98a2b3;stroke-width:1}}.svg-label{{font:12px Arial;fill:#475467}}.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}}.chart-legend{{font-size:12px;color:#475467}}.chart-legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}}@media(max-width:850px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}@media print{{@page{{size:A3 landscape;margin:10mm}}body{{background:#fff;font-size:9px}}main{{max-width:none;padding:0}}.toolbar{{display:none}}.tab-panel,.tab-panel.active{{display:block!important;break-before:page}}.tab-panel:first-of-type{{break-before:auto}}.card,.kpi{{box-shadow:none;break-inside:avoid}}.table-wrap{{max-height:none;overflow:visible}}.data-table{{font-size:7px}}.data-table th{{position:static;white-space:normal;padding:4px}}.data-table td{{white-space:normal;overflow-wrap:anywhere;padding:3px}}}}</style></head>
<body><main><header><h1>Indicador 01 · Validación de tarifas MCP</h1><p class="muted">Período evaluado: {html.escape(config['periodo_evaluado'])} · Ejecutado: {datetime.now():%d/%m/%Y %H:%M} · Tiempo de cálculo y copia de fuentes: {segundos_ejecucion:.2f} segundos · Versión {VERSION}</p><p class="validation-status">Información en proceso de validación. La comparación usa el mes evaluado y los dos meses calendario anteriores; s/d = sin información.</p></header>
<div class="toolbar"><nav>{''.join(botones)}</nav><div class="export-actions"><a class="export-button" href="resultado_indicador.pdf" download>Descargar PDF</a><a class="export-button excel" href="resultado_indicador.xlsx" download>Descargar Excel</a></div></div>{comparativo}{''.join(paneles)}<section class="card"><h2>Fuentes utilizadas</h2><ul>{fuentes_html}</ul></section></main><script>document.querySelectorAll('.tab-button').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('.tab-button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.tab-panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.target).classList.add('active');window.scrollTo(0,0)}}));</script></body></html>'''
    css_compacto = '<style>.mini-chart{display:block;width:210px;max-width:100%;height:68px;margin-top:3px}.spark-label{font:10px Arial;fill:#667085}.spark-caption{font-size:11px;color:#667085;margin-top:1px;min-height:14px}.kpi{margin-top:0;min-width:0;padding:13px;min-height:144px}.kpis{margin:16px 0}.value{font-size:clamp(17px,1.7vw,24px);overflow-wrap:anywhere}.validation-status{font-size:12px;color:#6a5118}.total-alertas{font-size:12px;color:#14395b}.fuentes-alerta{color:#805000;font-size:12px}@media print{.mini-chart{height:58px;width:180px}.kpi{min-height:118px}.value{font-size:20px}.card{break-inside:auto}.kpis{break-inside:avoid}}</style>'
    # Las notas sobre fuentes, cobertura histórica o conversión de archivos son
    # insumos de Auditoría Interna. No se incorporan al HTML que se comparte con
    # el auditado; se conservan en nota_auditoria_interna.txt y metadatos.
    documento = documento.replace('</head>', css_compacto + '</head>', 1)
    ruta.write_text(documento, encoding="utf-8")
    return {"indicator_id": "ING-01", "version": VERSION, "period": config["periodo_evaluado"], "generated_at": datetime.now().isoformat(timespec="microseconds"), "execution_seconds": round(segundos_ejecucion, 2), "validation_status": "En proceso de validación", "warnings": [], "metrics": {"evaluated": len(evaluados), "operations": len(operaciones), "additions": len(adiciones)}, "indicators": metricas, "comparison": series}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def raiz_predeterminada() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parents[1]


def inicializar(raiz: Path) -> None:
    for carpeta in [raiz / "fuentes" / "operaciones", raiz / "fuentes" / "adiciones", raiz / "fuentes" / "parametros", raiz / "resultados"]:
        carpeta.mkdir(parents=True, exist_ok=True)
    config = raiz / "fuentes" / "parametros" / "configuracion_ejecucion.json"
    if not config.exists():
        config.write_text(json.dumps({"periodo_evaluado": "2025-11", "tolerancia_cop": 1}, indent=2), encoding="utf-8")
    print(f"Estructura preparada en: {raiz}")


def cargar_configuracion(raiz: Path) -> dict:
    ruta = raiz / "fuentes" / "parametros" / "configuracion_ejecucion.json"
    if not ruta.exists():
        raise FileNotFoundError("Falta fuentes/parametros/configuracion_ejecucion.json. Ejecute primero --inicializar.")
    config = json.loads(ruta.read_text(encoding="utf-8"))
    if not re.fullmatch(r"\d{4}-\d{2}", str(config.get("periodo_evaluado", ""))):
        raise ValueError("periodo_evaluado debe tener formato AAAA-MM.")
    config["tolerancia_cop"] = float(config.get("tolerancia_cop", 1))
    validar_periodo(config["periodo_evaluado"])
    if not math.isfinite(config["tolerancia_cop"]) or config["tolerancia_cop"] < 0:
        raise ValueError("tolerancia_cop debe ser un número finito mayor o igual a cero.")
    return config


def validar_periodo(texto: str) -> pd.Period:
    if not re.fullmatch(r"\d{4}-\d{2}", texto):
        raise ValueError("El período debe tener formato AAAA-MM.")
    return pd.Period(texto, freq="M")


def archivos_xlsx(carpeta: Path) -> list[Path]:
    return sorted(p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() == ".xlsx" and not p.name.startswith("~$")) if carpeta.exists() else []


def depurar_repetidos(datos: pd.DataFrame, claves: list[str], nombre: str) -> tuple[pd.DataFrame, int]:
    """Un archivo consolidado y uno mensual pueden contener el mismo registro."""
    negocio = [c for c in datos.columns if not c.startswith("archivo_")]
    depurados = datos.drop_duplicates(subset=negocio).copy()
    conflicto = depurados.duplicated(subset=claves, keep=False)
    if conflicto.any():
        ejemplos = depurados.loc[conflicto, claves].drop_duplicates().head(5).astype(str).agg(" / ".join, axis=1).tolist()
        raise ValueError(f"{nombre}: registros con la misma clave y datos diferentes ({'; '.join(ejemplos)}). Revise las fuentes superpuestas antes de calcular.")
    return depurados.reset_index(drop=True), len(datos) - len(depurados)


def incoherencias_coherencia_base(eventos: pd.DataFrame) -> pd.DataFrame:
    """Revisa coherencia interna del reporte antes de aplicar las tarifas CUB.

    El porcentaje opcional reportado por SIB no reemplaza la tarifa real
    calculada ni la esperada CUB. Sirve para detectar una fuente contradictoria,
    por ejemplo la pérdida del separador decimal al convertir un archivo.
    """
    operaciones = eventos.loc[eventos["tipo_registro"].eq("Operación")].copy()
    hallazgos = []
    for punta in ("compra", "venta"):
        campo = f"tarifa_{punta}_reportada"
        if campo not in operaciones:
            continue
        calculo_reportado = operaciones["valor_base"] * operaciones[campo]
        aplicado = operaciones[f"registro_{punta}_aplicado"]
        diferencia = (calculo_reportado - aplicado).abs()
        # Se admite redondeo del reporte: COP 100 o 0,001 % del valor base,
        # el mayor de ambos. Esto detecta pérdida material de separadores.
        umbral = operaciones["valor_base"].abs().mul(0.00001).clip(lower=100)
        columnas_salida = ["operacion", "valor_base"]
        # La columna se incorpora durante la lectura de archivos; mantener un
        # valor vacío permite reutilizar este control sobre tablas en memoria.
        if "archivo_operacion" not in operaciones.columns:
            operaciones["archivo_operacion"] = ""
        columnas_salida.append("archivo_operacion")
        incoherentes = operaciones.loc[diferencia.gt(umbral) & operaciones[campo].notna() & aplicado.notna(), columnas_salida].copy()
        if not incoherentes.empty:
            incoherentes["punta"] = punta
            incoherentes["diferencia_interna"] = diferencia.loc[incoherentes.index]
            hallazgos.append(incoherentes)
    return pd.concat(hallazgos, ignore_index=True) if hallazgos else pd.DataFrame(columns=["operacion", "valor_base", "archivo_operacion", "punta", "diferencia_interna"])


def validar_coherencia_base(eventos: pd.DataFrame) -> None:
    incoherentes = incoherencias_coherencia_base(eventos)
    if not incoherentes.empty:
        ejemplos = "; ".join(f'{r.operacion}: base {money(r.valor_base)}' for r in incoherentes.drop_duplicates("operacion").head(5).itertuples())
        raise ValueError(f"Fuente de operaciones incoherente: valor_negocio x porc_registro no concilia materialmente con el cobro reportado ({ejemplos}). Revise la conversión y los datos de origen antes de calcular; no se corrigen valores automáticamente.")


def cargar_datos(raiz: Path) -> dict:
    """Carga únicamente XLSX. Se reutiliza en todos los meses de una corrida."""
    ops_dir = raiz / "fuentes" / "operaciones"
    adi_dir = raiz / "fuentes" / "adiciones"
    par_dir = raiz / "fuentes" / "parametros"
    archivos_ops, archivos_adi, archivos_tar = (archivos_xlsx(p) for p in (ops_dir, adi_dir, par_dir))
    if not archivos_ops or not archivos_adi or not archivos_tar:
        raise FileNotFoundError("Se requiere al menos un XLSX en operaciones, adiciones y parametros. Guarde los archivos XLS/XLSB como Libro de Excel (*.xlsx) desde Excel.")
    if len(archivos_tar) != 1:
        raise ValueError("Deje un único PT tarifario XLSX en fuentes/parametros para evitar seleccionar una versión de tarifas arbitrariamente.")
    operaciones_brutas = pd.concat([leer_operaciones(p) for p in archivos_ops], ignore_index=True)
    adiciones_brutas = pd.concat([leer_adiciones(p) for p in archivos_adi], ignore_index=True)
    operaciones, dup_ops = depurar_repetidos(operaciones_brutas, ["operacion"], "Operaciones")
    adiciones, dup_adi = depurar_repetidos(adiciones_brutas, ["operacion", "no_adicion"], "Adiciones")
    if operaciones["fecha_operacion"].isna().any() or adiciones["fecha_solicitud"].isna().any():
        raise ValueError("Hay operaciones o adiciones sin fecha válida para asignar el período. Revise FechaOperacion y Fecha Solicitud.")
    tarifas = extraer_tarifas(archivos_tar[0])
    originales, descartadas = preparar_originales(operaciones)
    # Una adición vinculada a una operación conocida de Mercop u otro mercado
    # se excluye del universo MCP; una original no encontrada queda pendiente.
    ids_otro_mercado = set(operaciones.loc[operaciones["naturaleza"].isna(), "operacion"])
    fuera_mcp = adiciones.loc[adiciones["operacion"].isin(ids_otro_mercado)].copy()
    adiciones_mcp = adiciones.loc[~adiciones["operacion"].isin(ids_otro_mercado)].copy()
    adiciones_clas = clasificar_adiciones(adiciones_mcp, originales)
    eventos = pd.concat([originales, adiciones_clas], ignore_index=True, sort=False)
    ignorados = [str(p.relative_to(raiz)) for carpeta in (ops_dir, adi_dir) for p in sorted(carpeta.iterdir()) if p.suffix.lower() in {".xls", ".xlsb"} and not p.name.startswith("~$")]
    control = {"registros_operaciones_cargados": len(operaciones_brutas), "registros_adiciones_cargados": len(adiciones_brutas), "duplicados_exactos_operaciones_excluidos": dup_ops, "duplicados_exactos_adiciones_excluidos": dup_adi, "operaciones_fuera_mcp": len(descartadas), "adiciones_fuera_mcp": len(fuera_mcp), "archivos_no_leidos": ignorados}
    return {"eventos": eventos, "tarifas": tarifas, "fuentes": archivos_ops + archivos_adi + archivos_tar, "control": control, "fuera_mcp": fuera_mcp}


def crear_carpeta_resultado(raiz: Path, periodo: str) -> Path:
    """Genera una ruta corta para evitar el límite de Windows al guardar evidencia."""
    base = raiz / "resultados" / f"{periodo}_{datetime.now():%Y%m%d%H%M%S}"
    candidata, consecutivo = base, 2
    while candidata.exists():
        candidata = Path(f"{base}_{consecutivo}")
        consecutivo += 1
    candidata.mkdir(parents=True)
    return candidata


def copiar_fuentes_resultado(fuentes: list[Path], raiz: Path, carpeta: Path) -> Path:
    """Conserva fuentes con nombres cortos y trazables en la carpeta de salida."""
    copia = carpeta / "fuentes"
    copia.mkdir()
    raiz_fuentes = raiz / "fuentes"
    for fuente in fuentes:
        relativo = fuente.relative_to(raiz_fuentes)
        categoria = relativo.parts[0]
        destino = copia / f"{categoria}__{fuente.name}"
        if destino.exists():
            raise FileExistsError(f"Ya existe una copia de fuente con el nombre {destino.name}.")
        shutil.copy2(fuente, destino)
    return copia


def manifiesto_fuentes(fuentes: list[Path], raiz: Path) -> list[dict]:
    """Trazabilidad reproducible sin duplicar las bases de datos por corrida."""
    return [{
        "archivo": fuente.name,
        "ruta": str(fuente.relative_to(raiz)),
        "sha256": sha256(fuente),
        "tamano_bytes": fuente.stat().st_size,
    } for fuente in fuentes]


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def escribir_nota_auditoria(ruta: Path, periodo: str, notas: list[str]) -> None:
    """Guarda alertas técnicas internas fuera de los entregables compartibles."""
    if not notas:
        return
    contenido = [
        "NOTA PARA AUDITORÍA INTERNA — NO COMPARTIR CON EL AUDITADO",
        f"Indicador 01 - Tarifas MCP | Período: {periodo}",
        "",
        "Estas notas corresponden a controles técnicos de fuentes, cobertura o antecedentes históricos. No alteran por sí mismas la conclusión del período evaluado.",
        "",
    ]
    contenido.extend(f"- {nota}" for nota in notas)
    ruta.write_text("\n".join(contenido) + "\n", encoding="utf-8")


def ejecutar(raiz: Path, periodo_evaluado: str | None = None, datos: dict | None = None) -> tuple[Path, float]:
    inicio_ejecucion = perf_counter()
    config = cargar_configuracion(raiz)
    if periodo_evaluado is not None:
        config["periodo_evaluado"] = periodo_evaluado
    periodo = validar_periodo(config["periodo_evaluado"])
    par_dir = raiz / "fuentes" / "parametros"
    datos = cargar_datos(raiz) if datos is None else datos
    # Las operaciones anteriores al mes permanecen para reconstruir acumulados.
    eventos = datos["eventos"].loc[datos["eventos"]["fecha_evento"] <= periodo.end_time].copy()
    tarifas = datos["tarifas"]
    calculados = recalcular(eventos, tarifas, config["tolerancia_cop"])
    es_operacion_periodo = calculados["tipo_registro"].eq("Operación") & (calculados["fecha_operacion"].dt.to_period("M") == periodo)
    es_adicion_periodo = calculados["tipo_registro"].eq("Adición") & (calculados["fecha_solicitud"].dt.to_period("M") == periodo)
    evaluados = calculados.loc[es_operacion_periodo | es_adicion_periodo].copy()
    # El control bloqueante se aplica únicamente a la operación del mes evaluado.
    # Los históricos se usan para acumulados y búsqueda de originales.
    validar_coherencia_base(evaluados)
    avisos = []
    historicos = eventos.loc[~eventos["tipo_registro"].eq("Operación") | (eventos["fecha_operacion"].dt.to_period("M") != periodo)]
    inconsistencias_historicas = incoherencias_coherencia_base(historicos)
    if not inconsistencias_historicas.empty:
        operaciones_historicas = inconsistencias_historicas["operacion"].nunique()
        ejemplos = ", ".join(inconsistencias_historicas["operacion"].drop_duplicates().head(5))
        avisos.append(f"Control histórico: {operaciones_historicas} operaciones presentan diferencias internas entre valor, tarifa reportada y cobro ({ejemplos}). Se usan solo como antecedente; revise su efecto si soportan acumulados de adiciones.")
    if datos["control"]["archivos_no_leidos"]:
        avisos.append("Archivos XLS/XLSB no utilizados: " + "; ".join(datos["control"]["archivos_no_leidos"]) + ". Guárdelos como XLSX para incorporarlos a la búsqueda histórica.")
    sin_original = evaluados.loc[evaluados["tipo_registro"].eq("Adición") & evaluados["original_naturaleza"].isna()]
    if not sin_original.empty:
        avisos.append(f"Cobertura parcial: {len(sin_original)} adiciones del mes no tienen operación original disponible; no se concluye sobre sus tarifas. Revise la integridad histórica antes de validar los acumulados.")
    if evaluados.empty:
        avisos.append("Sin población MCP en las fuentes para el mes seleccionado; este resultado no acredita ausencia de errores.")
    carpeta = crear_carpeta_resultado(raiz, config["periodo_evaluado"])
    fuentes = datos["fuentes"] + [par_dir / "configuracion_ejecucion.json"]
    # Las fuentes permanecen en su ubicación controlada. Cada salida conserva
    # ruta, tamaño y SHA-256, evitando copiar bases completas por cada mes.
    configuracion_efectiva = json.dumps(config, ensure_ascii=False, sort_keys=True)
    escribir_nota_auditoria(carpeta / "nota_auditoria_interna.txt", config["periodo_evaluado"], avisos)
    shutil.copy2(Path(__file__), carpeta / "codigo_utilizado.py")
    salida_html = carpeta / "dashboard.html"
    segundos_ejecucion = perf_counter() - inicio_ejecucion
    resultado = html_reporte_v2(salida_html, evaluados, config, fuentes, segundos_ejecucion, raiz / "resultados")
    salida_excel = carpeta / "resultado_indicador.xlsx"
    salida_pdf = carpeta / "resultado_indicador.pdf"
    exportar_excel(salida_excel, evaluados, config, fuentes, resultado["indicators"])
    exportar_pdf(salida_pdf, evaluados, config, fuentes)
    resultado["export_files"] = {"pdf": salida_pdf.name, "excel": salida_excel.name}
    (carpeta / "detalle_calculo.json").write_text(evaluados.to_json(orient="records", date_format="iso", force_ascii=False, indent=2), encoding="utf-8")
    metadatos = {"version_codigo": VERSION, "periodo_evaluado": config["periodo_evaluado"], "fuentes": manifiesto_fuentes(fuentes, raiz), "configuracion_efectiva": config, "configuracion_efectiva_sha256": sha256_texto(configuracion_efectiva), "codigo_sha256": sha256(Path(__file__)), "archivos_exportados": [{"archivo": salida_excel.name, "sha256": sha256(salida_excel)}, {"archivo": salida_pdf.name, "sha256": sha256(salida_pdf)}], "control_carga": datos["control"], "notas_auditor": avisos}
    segundos_total = round(perf_counter() - inicio_ejecucion, 2)
    metadatos["tiempo_ejecucion_segundos"] = segundos_total
    resultado["execution_seconds"] = segundos_total
    resultado["control_carga"] = datos["control"]
    (carpeta / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (carpeta / "metadatos_ejecucion.json").write_text(json.dumps(metadatos, ensure_ascii=False, indent=2), encoding="utf-8")
    return carpeta, metadatos["tiempo_ejecucion_segundos"]


def meses_con_operaciones(datos: dict) -> list[str]:
    """Meses AAAA-MM con al menos una operación del universo MCP ya cargado."""
    eventos = datos["eventos"]
    fechas = eventos.loc[eventos["tipo_registro"].eq("Operación"), "fecha_operacion"].dropna()
    return sorted({str(mes) for mes in fechas.dt.to_period("M")})


def main() -> int:
    parser = argparse.ArgumentParser(description="Indicador 01 - Tarifas MCP")
    parser.add_argument("--raiz", type=Path, default=raiz_predeterminada(), help="Carpeta principal de la aplicación.")
    parser.add_argument("--inicializar", action="store_true", help="Crea las carpetas de fuentes, resultados y la configuración inicial.")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--periodo", help="Calcula un mes AAAA-MM sin modificar la configuración principal.")
    grupo.add_argument("--desde", help="Primer mes AAAA-MM de una ejecución por rango.")
    parser.add_argument("--hasta", help="Último mes AAAA-MM; requiere --desde.")
    args = parser.parse_args()
    try:
        if args.inicializar:
            inicializar(args.raiz); return 0
        raiz = args.raiz.resolve()
        if bool(args.desde) != bool(args.hasta):
            raise ValueError("Para un rango indique tanto --desde como --hasta.")
        if args.desde:
            desde, hasta = validar_periodo(args.desde), validar_periodo(args.hasta)
            if desde > hasta:
                raise ValueError("El mes inicial debe ser anterior o igual al final.")
            periodos = [str(p) for p in pd.period_range(desde, hasta, freq="M")]
        else:
            periodos = [args.periodo or cargar_configuracion(raiz)["periodo_evaluado"]]
        for periodo in periodos:
            validar_periodo(periodo)
        inicio_lote = perf_counter()
        print(f"Indicador MCP v{VERSION}. Cargando fuentes XLSX...", flush=True)
        datos = cargar_datos(raiz)
        for periodo in periodos:
            print(f"Calculando {periodo}...", flush=True)
            carpeta, segundos = ejecutar(raiz, periodo, datos)
            print(f"Ejecución finalizada. Resultados: {carpeta}", flush=True)
            print(f"Tiempo de ejecución del mes (fuentes ya cargadas): {segundos:.2f} segundos", flush=True)
            metadatos = json.loads((carpeta / "metadatos_ejecucion.json").read_text(encoding="utf-8"))
            for nota in metadatos["notas_auditor"]:
                print(f"NOTA PARA AUDITOR: {nota}", flush=True)
        print(f"Tiempo total de ejecución (incluye carga de fuentes): {perf_counter() - inicio_lote:.2f} segundos")
        return 0
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
