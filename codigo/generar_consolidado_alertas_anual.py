#!/usr/bin/env python3
"""Genera, una sola vez, el consolidado anual de alertas del Indicador 01.

Lee la última corrida disponible de cada mes en resultados/ y no recalcula el
indicador ni modifica sus fuentes. El Excel resultante está dirigido a la
Administración y contiene únicamente alertas del período, no notas internas
de Auditoría.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


INDICADORES = ["IND-01", "IND-02", "IND-03", "IND-04", "IND-05"]
NOMBRES_INDICADOR = {
    "IND-01": "Registro de operación - punta compradora",
    "IND-02": "Registro de operación - punta vendedora",
    "IND-03": "Compensación y liquidación",
    "IND-04": "Registro de adición - punta compradora",
    "IND-05": "Registro de adición - punta vendedora",
}
MESES = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}


def texto(valor: object) -> str:
    if pd.isna(valor):
        return ""
    return str(valor)


def valor(valor: object) -> object:
    if pd.isna(valor):
        return None
    return valor.item() if hasattr(valor, "item") else valor


def fecha(valor_fecha: object) -> object:
    convertido = pd.to_datetime(valor_fecha, errors="coerce")
    return None if pd.isna(convertido) else convertido.to_pydatetime()


def nombre_mes(periodo: str) -> str:
    return f"{MESES[int(periodo[-2:])]} {periodo[:4]}"


def obtener_corridas_resultados(carpeta_resultados: Path, anio: int) -> dict[str, Path]:
    """Escoge la última corrida de cada mes que tenga detalle y resultado."""
    patron = re.compile(rf"^({anio}-(?:0[1-9]|1[0-2]))_")
    candidatas: dict[str, list[Path]] = {}
    if not carpeta_resultados.exists():
        raise FileNotFoundError(f"No existe la carpeta de resultados: {carpeta_resultados}")
    for carpeta in carpeta_resultados.iterdir():
        coincidencia = patron.match(carpeta.name)
        if not carpeta.is_dir() or not coincidencia:
            continue
        if not (carpeta / "resultado.json").exists() or not (carpeta / "detalle_calculo.json").exists():
            continue
        candidatas.setdefault(coincidencia.group(1), []).append(carpeta)
    return {periodo: max(carpetas, key=lambda p: p.stat().st_mtime) for periodo, carpetas in candidatas.items()}


def cargar_corrida(periodo: str, carpeta: Path) -> tuple[pd.DataFrame, list[dict], dict]:
    detalle = pd.DataFrame(json.loads((carpeta / "detalle_calculo.json").read_text(encoding="utf-8")))
    resultado = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
    resumen = []
    for indicador in INDICADORES:
        metricas = resultado.get("indicators", {}).get(indicador, {})
        resumen.append({
            "Mes": nombre_mes(periodo),
            "Período": periodo,
            "Indicador": indicador,
            "Descripción": NOMBRES_INDICADOR[indicador],
            "Población": metricas.get("population", 0),
            "Alertas (registros)": metricas.get("alerts", 0),
            "No evaluables": metricas.get("not_evaluable", 0),
            "Diferencia neta alertas": metricas.get("alert_difference_net", 0),
        })
    control = {
        "Mes": nombre_mes(periodo),
        "Período": periodo,
        "Generado": resultado.get("generated_at", ""),
        "Versión": resultado.get("version", ""),
    }
    return detalle, resumen, control


def extraer_alertas(detalle: pd.DataFrame, periodo: str) -> pd.DataFrame:
    """Convierte alertas de las cinco vistas en un detalle homogéneo por punta."""
    especificaciones = [
        ("IND-01", "Operación", "Registro de operación", "Compradora", "resultado_registro_compra", "motivo_registro_compra", "tarifa_compra_aplicada", "tarifa_compra_esperada", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra"),
        ("IND-02", "Operación", "Registro de operación", "Vendedora", "resultado_registro_venta", "motivo_registro_venta", "tarifa_venta_aplicada", "tarifa_venta_esperada", "registro_venta_aplicado", "registro_venta_esperado", "diferencia_venta"),
        ("IND-03", None, "Compensación y liquidación", "Compradora", "resultado_cyl_compra", "motivo_cyl_compra", "tarifa_cyl_compra_aplicada", "tarifa_cyl_compra_esperada", "cyl_compra_aplicado", "cyl_compra_esperado", "diferencia_cyl_compra"),
        ("IND-03", None, "Compensación y liquidación", "Vendedora", "resultado_cyl_venta", "motivo_cyl_venta", "tarifa_cyl_venta_aplicada", "tarifa_cyl_venta_esperada", "cyl_venta_aplicado", "cyl_venta_esperado", "diferencia_cyl_venta"),
        ("IND-04", "Adición", "Registro de adición", "Compradora", "resultado_registro_compra", "motivo_registro_compra", "tarifa_compra_aplicada", "tarifa_compra_esperada", "registro_compra_aplicado", "registro_compra_esperado", "diferencia_compra"),
        ("IND-05", "Adición", "Registro de adición", "Vendedora", "resultado_registro_venta", "motivo_registro_venta", "tarifa_venta_aplicada", "tarifa_venta_esperada", "registro_venta_aplicado", "registro_venta_esperado", "diferencia_venta"),
    ]
    registros = []
    for indicador, tipo, servicio, punta, campo_estado, campo_motivo, tarifa_aplicada, tarifa_esperada, cobro_aplicado, cobro_esperado, diferencia in especificaciones:
        seleccion = detalle.loc[detalle[campo_estado].eq("Alerta")].copy()
        if tipo is not None:
            seleccion = seleccion.loc[seleccion["tipo_registro"].eq(tipo)]
        for _, fila in seleccion.iterrows():
            fecha_evento = fila.get("fecha_operacion") if fila.get("tipo_registro") == "Operación" else fila.get("fecha_solicitud")
            registros.append({
                "Mes": nombre_mes(periodo), "Período": periodo, "Indicador": indicador,
                "Servicio": servicio, "Tipo de registro": fila.get("tipo_registro"), "Punta": punta,
                "Operación": texto(fila.get("operacion")), "No. adición": texto(fila.get("no_adicion")),
                "Fecha del evento": fecha(fecha_evento), "Naturaleza": texto(fila.get("naturaleza")),
                "Mandante comprador": texto(fila.get("mandante_compra")), "Acumulado previo": valor(fila.get("acumulado_previo")),
                "Valor base": valor(fila.get("valor_base")), "Tarifa aplicada": valor(fila.get(tarifa_aplicada)),
                "Tarifa esperada": valor(fila.get(tarifa_esperada)), "Cobro aplicado": valor(fila.get(cobro_aplicado)),
                "Cobro esperado": valor(fila.get(cobro_esperado)), "Diferencia": valor(fila.get(diferencia)),
                "Motivo": texto(fila.get(campo_motivo)), "Artículo CUB": texto(fila.get("articulo_cub")),
                "Página CUB": texto(fila.get("pagina_cub")),
            })
    columnas = ["Mes", "Período", "Indicador", "Servicio", "Tipo de registro", "Punta", "Operación", "No. adición", "Fecha del evento", "Naturaleza", "Mandante comprador", "Acumulado previo", "Valor base", "Tarifa aplicada", "Tarifa esperada", "Cobro aplicado", "Cobro esperado", "Diferencia", "Motivo", "Artículo CUB", "Página CUB"]
    return pd.DataFrame(registros, columns=columnas)


def aplicar_encabezado(hoja, fila: int, inicio: int, fin: int) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    for columna in range(inicio, fin + 1):
        celda = hoja.cell(fila, columna)
        celda.fill = PatternFill("solid", fgColor="14395B")
        celda.font = Font(color="FFFFFF", bold=True)
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def escribir_tabla(hoja, fila: int, dataframe: pd.DataFrame, anchos: dict[str, float]) -> int:
    from openpyxl.styles import Alignment, Border, Side
    columnas = list(dataframe.columns)
    for columna, nombre in enumerate(columnas, 1):
        hoja.cell(fila, columna, nombre)
    aplicar_encabezado(hoja, fila, 1, len(columnas))
    borde = Border(bottom=Side(style="thin", color="D9E2EC"))
    for fila_excel, (_, registro) in enumerate(dataframe.iterrows(), fila + 1):
        for columna, nombre in enumerate(columnas, 1):
            celda = hoja.cell(fila_excel, columna, valor(registro[nombre]))
            celda.border = borde
            celda.alignment = Alignment(vertical="top", wrap_text=nombre in {"Motivo", "Servicio"})
            if nombre in {"Acumulado previo", "Valor base", "Cobro aplicado", "Cobro esperado", "Diferencia", "Diferencia neta alertas", "Diferencia absoluta alertas"}:
                celda.number_format = '#,##0;[Red]-#,##0'
            elif nombre in {"Tarifa aplicada", "Tarifa esperada"}:
                celda.number_format = '0.000%'
            elif nombre == "Fecha del evento":
                celda.number_format = 'dd/mm/yyyy'
    for indice, nombre in enumerate(columnas, 1):
        hoja.column_dimensions[chr(64 + indice) if indice <= 26 else "A"].width = anchos.get(nombre, max(12, min(24, len(nombre) + 2)))
    return fila + len(dataframe) + 2


def exportar_excel(ruta: Path, resumen: pd.DataFrame, detalle: pd.DataFrame, corridas: pd.DataFrame, anio: int) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Resumen mensual"
    hoja.sheet_properties.tabColor = "14395B"
    hoja["A1"] = f"Consolidado anual de alertas — Indicador 01 Tarifas MCP ({anio})"
    hoja["A1"].font = Font(color="FFFFFF", bold=True, size=14)
    hoja["A1"].fill = PatternFill("solid", fgColor="14395B")
    hoja.merge_cells("A1:H1")
    hoja["A2"] = "Entrega inicial para validación de la Administración. Incluye la última corrida disponible de cada mes y únicamente registros clasificados como Alerta."
    hoja["A2"].font = Font(italic=True, color="667085")
    hoja.merge_cells("A2:H2")
    hoja["A4"] = "Resumen por mes"; hoja["A4"].font = Font(bold=True, color="14395B")
    resumen_mes = resumen.groupby(["Mes", "Período"], as_index=False).agg({"Alertas (registros)": "sum", "Diferencia neta alertas": "sum"})
    resumen_mes["Diferencia absoluta alertas"] = detalle.groupby("Período")["Diferencia"].apply(lambda x: x.abs().sum()).reindex(resumen_mes["Período"], fill_value=0).to_numpy()
    resumen_mes = resumen_mes[["Mes", "Período", "Alertas (registros)", "Diferencia neta alertas", "Diferencia absoluta alertas"]].sort_values("Período", kind="stable")
    siguiente = escribir_tabla(hoja, 5, resumen_mes, {"Mes": 18, "Período": 12, "Alertas (registros)": 20, "Diferencia neta alertas": 24, "Diferencia absoluta alertas": 26})
    hoja.cell(siguiente, 1, "Resumen por indicador y mes").font = Font(bold=True, color="14395B")
    escribir_tabla(hoja, siguiente + 1, resumen, {"Mes": 18, "Período": 12, "Indicador": 12, "Descripción": 45, "Población": 14, "Alertas (registros)": 20, "No evaluables": 16, "Diferencia neta alertas": 24})
    hoja.freeze_panes = "A5"

    detalle_hoja = libro.create_sheet("Detalle de alertas")
    detalle_hoja.sheet_properties.tabColor = "1677B8"
    detalle_hoja["A1"] = f"Detalle de alertas — {anio}"
    detalle_hoja["A1"].font = Font(color="FFFFFF", bold=True, size=13)
    detalle_hoja["A1"].fill = PatternFill("solid", fgColor="14395B")
    detalle_hoja.merge_cells("A1:H1")
    detalle_hoja["A2"] = "Cada fila corresponde a una validación con alerta. Diferencia = cobro aplicado − cobro esperado."
    detalle_hoja["A2"].font = Font(italic=True, color="667085")
    detalle_hoja.merge_cells("A2:H2")
    escribir_tabla(detalle_hoja, 4, detalle, {"Mes": 16, "Período": 12, "Indicador": 12, "Servicio": 28, "Tipo de registro": 16, "Punta": 14, "Operación": 15, "No. adición": 13, "Fecha del evento": 16, "Naturaleza": 14, "Mandante comprador": 20, "Acumulado previo": 20, "Valor base": 18, "Tarifa aplicada": 15, "Tarifa esperada": 15, "Cobro aplicado": 18, "Cobro esperado": 18, "Diferencia": 18, "Motivo": 42, "Artículo CUB": 18, "Página CUB": 14})
    detalle_hoja.freeze_panes = "A5"
    if not detalle.empty:
        tabla = Table(displayName="DetalleAlertas", ref=f"A4:U{len(detalle) + 4}")
        tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        detalle_hoja.add_table(tabla)

    control = libro.create_sheet("Corridas incluidas")
    control.sheet_properties.tabColor = "98A2B3"
    control["A1"] = "Corridas incluidas en el consolidado"
    control["A1"].font = Font(color="FFFFFF", bold=True, size=13)
    control["A1"].fill = PatternFill("solid", fgColor="14395B")
    control.merge_cells("A1:D1")
    escribir_tabla(control, 3, corridas, {"Mes": 18, "Período": 12, "Generado": 28, "Versión": 14})
    control.freeze_panes = "A4"
    libro.save(ruta)


def generar(raiz: Path, anio: int) -> Path:
    resultados = raiz / "resultados"
    corridas = obtener_corridas_resultados(resultados, anio)
    if not corridas:
        raise FileNotFoundError(f"No se encontraron corridas {anio}-MM con resultado.json y detalle_calculo.json en {resultados}.")
    detalle_anual, resumen_anual, control_anual = [], [], []
    for periodo, carpeta in sorted(corridas.items()):
        detalle, resumen, control = cargar_corrida(periodo, carpeta)
        detalle_anual.append(extraer_alertas(detalle, periodo))
        resumen_anual.extend(resumen)
        control_anual.append(control)
    detalle = pd.concat(detalle_anual, ignore_index=True) if detalle_anual else pd.DataFrame()
    if not detalle.empty:
        detalle = detalle.sort_values(["Período", "Indicador", "Operación", "No. adición", "Punta"], kind="stable").reset_index(drop=True)
    resumen = pd.DataFrame(resumen_anual).sort_values(["Período", "Indicador"], kind="stable")
    control = pd.DataFrame(control_anual).sort_values("Período", kind="stable")
    destino = resultados / f"Consolidado_alertas_{anio}.xlsx"
    exportar_excel(destino, resumen, detalle, control, anio)
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida alertas anuales del Indicador 01 - Tarifas MCP.")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1], help="Carpeta principal Indicador_01_Tarifas_MCP.")
    parser.add_argument("--anio", type=int, default=2026, help="Año a consolidar.")
    args = parser.parse_args()
    try:
        salida = generar(args.raiz.resolve(), args.anio)
        print(f"Consolidado generado: {salida}")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
