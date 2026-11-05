"""Pruebas de frontera de la clasificación de adiciones.

Ejecutar desde la carpeta principal:
    python pruebas/test_reglas_adiciones.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo"))
from indicador_01_tarifas_mcp import clasificar_adiciones


def original(operacion: str, naturaleza: str, entrega: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "operacion": operacion, "negocio": "FRWMCP" if naturaleza == "Forward" else "DISMCP",
        "naturaleza": naturaleza, "fecha_entrega_original": pd.Timestamp(entrega),
        "fecha_operacion": pd.Timestamp("2025-01-01"), "mandante_compra": "900000001",
        "archivo_operacion": "operaciones_prueba.xlsx",
    }])


def adicion(operacion: str, entrega: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "operacion": operacion, "no_adicion": "1", "valor_base": 100,
        "registro_compra_aplicado": 0.3, "registro_venta_aplicado": 0.3,
        "fecha_solicitud": pd.Timestamp("2025-11-01"), "fecha_entrega_adicion": pd.Timestamp(entrega),
        "archivo_adicion": "adiciones_prueba.xlsx",
    }])


def verificar(operacion: str, naturaleza_original: str, entrega_adicion: str, esperada: str) -> None:
    resultado = clasificar_adiciones(adicion(operacion, entrega_adicion), original(operacion, naturaleza_original, "2025-06-30"))
    assert resultado.loc[0, "naturaleza"] == esperada, resultado.loc[0].to_dict()
    assert resultado.loc[0, "estado_clasificacion"] == "Clasificada", resultado.loc[0].to_dict()


if __name__ == "__main__":
    verificar("1", "Forward", "2025-06-30", "Forward")
    verificar("2", "Disponible", "2025-06-30", "Disponible")
    verificar("3", "Disponible", "2025-07-30", "Disponible")
    verificar("4", "Disponible", "2025-07-31", "Forward")
    anterior = clasificar_adiciones(adicion("5", "2025-06-29"), original("5", "Disponible", "2025-06-30"))
    assert anterior.loc[0, "estado_clasificacion"] == "No evaluable", anterior.loc[0].to_dict()
    print("Pruebas de frontera superadas: Forward, 0, 30, 31 y fecha anterior.")
