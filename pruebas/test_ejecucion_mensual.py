"""Controles de calendario, fuentes superpuestas y acumulados; no usa datos reales."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo"))
import indicador_01_tarifas_mcp as m


class PruebasMensuales(unittest.TestCase):
    def test_calendario_faltante_y_ultima_corrida(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            for nombre, periodo, fecha, alertas in [
                ("nov", "2025-11", "2026-01-01", 8),
                ("jun_antiguo", "2026-06", "2026-07-01", 7),
                ("jun_nuevo", "2026-06", "2026-07-02", 2),
            ]:
                p = raiz / nombre
                p.mkdir()
                (p / "resultado.json").write_text(json.dumps({"period": periodo, "generated_at": fecha, "indicators": {"IND-01": {"population": 10, "alerts": alertas, "not_evaluable": 0, "alert_difference_net": -50}}}))
            actual = {"IND-01": {"population": 12, "alerts": 0, "not_evaluable": 0, "alert_difference_net": 0}}
            filas = m.cargar_comparativo_tres_meses(raiz, "2026-08", actual)["IND-01"]
            self.assertEqual([f["Período"] for f in filas], ["2026-06", "2026-07", "2026-08"])
            self.assertEqual(filas[0]["Tarifas mal aplicadas"], 2)
            self.assertIsNone(filas[1]["Tarifas mal aplicadas"])
            self.assertIn("Sin período anterior", filas[2]["Tendencia de alertas"])
            svg = m.mini_grafica(filas, "_diferencia_neta", m.money)
            self.assertIn("s/d", svg)
            self.assertIn("COP -50", svg)
            self.assertNotIn('height="-', svg)

    def test_fuentes_superpuestas_y_conflicto(self):
        filas = pd.DataFrame([{"operacion": "1", "valor_base": 100, "archivo_operacion": "anual.xlsx"}, {"operacion": "1", "valor_base": 100, "archivo_operacion": "enero.xlsx"}])
        salida, excluidos = m.depurar_repetidos(filas, ["operacion"], "Operaciones")
        self.assertEqual((len(salida), excluidos), (1, 1))
        filas.loc[1, "valor_base"] = 101
        with self.assertRaisesRegex(ValueError, "datos diferentes"):
            m.depurar_repetidos(filas, ["operacion"], "Operaciones")

    def test_acumulado_no_incluye_evento_evaluado(self):
        tarifas = pd.DataFrame([
            {"servicio": "Registro de operación", "naturaleza": "Forward", "punta": "Comprador", "minimo": 0, "maximo": 200_000_000_000, "tarifa": .003, "articulo_cub": "prueba", "pagina_cub": 1},
            {"servicio": "Registro de operación", "naturaleza": "Forward", "punta": "Comprador", "minimo": 200_000_000_000, "maximo": float("inf"), "tarifa": .0026, "articulo_cub": "prueba", "pagina_cub": 1},
        ])
        eventos = pd.DataFrame([{
            "operacion": str(i), "tipo_registro": "Operación", "no_adicion": None,
            "naturaleza": "Forward", "mandante_compra": "9001", "anio_acumulado": 2026,
            "fecha_evento": pd.Timestamp(fecha), "valor_base": valor,
            "registro_compra_aplicado": 0, "registro_venta_aplicado": 0,
            "cyl_compra_aplicado": 0, "cyl_venta_aplicado": 0, "estado_clasificacion": None,
        } for i, fecha, valor in [(1, "2026-01-01", 200_000_000_000), (2, "2026-02-01", 10), (3, "2026-03-01", 20)]])
        salida = m.recalcular(eventos, tarifas, 1)
        self.assertEqual(salida["acumulado_previo"].tolist(), [0, 200_000_000_000, 200_000_000_010])
        self.assertEqual(salida["tarifa_compra_esperada"].tolist(), [.003, .003, .0026])

    def test_mes_invalido(self):
        with self.assertRaises(ValueError):
            m.validar_periodo("2026-13")

    def test_conversion_decimal_incoherente(self):
        fila = pd.DataFrame([{"operacion": "107499099", "tipo_registro": "Operación", "valor_base": 10946620084029900.0, "registro_compra_aplicado": 32839860, "registro_venta_aplicado": 32839860, "tarifa_compra_reportada": .003, "tarifa_venta_reportada": .003}])
        with self.assertRaisesRegex(ValueError, "107499099"):
            m.validar_coherencia_base(fila, 1)
        fila.loc[0, "valor_base"] = 10946620084.029972
        m.validar_coherencia_base(fila, 1)

    def test_trazabilidad_cub_convierte_pagina_numerica_a_texto(self):
        pagina = pd.Series([""], dtype="string")
        pagina.loc[0] = m.texto_trazabilidad(43)
        self.assertEqual(pagina.loc[0], "43")
        self.assertEqual(m.texto_trazabilidad(pd.NA), "")

    def test_copia_de_fuentes_usa_ruta_corta_y_categoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / ("proyecto_" + "x" * 80)
            fuente = raiz / "fuentes" / "operaciones" / ("operaciones_" + "x" * 80 + ".xlsx")
            fuente.parent.mkdir(parents=True)
            fuente.write_text("fuente", encoding="utf-8")
            resultado = m.crear_carpeta_resultado(raiz, "2026-08")
            copia = m.copiar_fuentes_resultado([fuente], raiz, resultado)
            self.assertTrue((copia / f"operaciones__{fuente.name}").exists())
            self.assertLess(len(str(copia / f"operaciones__{fuente.name}")), len(str(resultado / "fuentes_utilizadas" / "operaciones" / fuente.name)))


if __name__ == "__main__":
    unittest.main()
