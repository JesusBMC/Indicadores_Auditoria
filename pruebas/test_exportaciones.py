"""Comprueba que los dos archivos descargables se generen y conserven las cinco vistas."""
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codigo"))
import indicador_01_tarifas_mcp as m


class PruebasExportaciones(unittest.TestCase):
    def test_excel_y_pdf(self):
        datos = pd.DataFrame([
            {"tipo_registro": "Operación", "operacion": "100", "no_adicion": None, "negocio": "FRWMCP", "naturaleza": "Forward", "mandante_compra": "9001", "fecha_operacion": pd.Timestamp("2026-08-01"), "fecha_evento": pd.Timestamp("2026-08-01"), "fecha_entrega_original": pd.Timestamp("2026-08-20"), "valor_base": 1_000_000, "acumulado_previo": 0, "tarifa_compra_aplicada": .003, "tarifa_compra_esperada": .003, "registro_compra_aplicado": 3_000, "registro_compra_esperado": 3_000, "diferencia_compra": 0, "resultado_registro_compra": "Conforme", "motivo_registro_compra": "", "tarifa_venta_aplicada": .003, "tarifa_venta_esperada": .003, "registro_venta_aplicado": 3_000, "registro_venta_esperado": 3_000, "diferencia_venta": 0, "resultado_registro_venta": "Conforme", "motivo_registro_venta": "", "tarifa_cyl_compra_aplicada": .0021, "tarifa_cyl_compra_esperada": .0021, "cyl_compra_aplicado": 2_100, "cyl_compra_esperado": 2_100, "diferencia_cyl_compra": 0, "resultado_cyl_compra": "Conforme", "motivo_cyl_compra": "", "tarifa_cyl_venta_aplicada": .0021, "tarifa_cyl_venta_esperada": .0021, "cyl_venta_aplicado": 2_100, "cyl_venta_esperado": 2_100, "diferencia_cyl_venta": 0, "resultado_cyl_venta": "Conforme", "motivo_cyl_venta": "", "resultado_cyl": "Conforme", "diferencia_cyl": 0, "archivo_operacion": "operaciones.xlsx"},
            {"tipo_registro": "Adición", "operacion": "100", "no_adicion": "1", "naturaleza": "Forward", "original_naturaleza": "Forward", "mandante_compra": "9001", "fecha_solicitud": pd.Timestamp("2026-08-05"), "fecha_evento": pd.Timestamp("2026-08-05"), "fecha_entrega_adicion": pd.Timestamp("2026-08-25"), "original_fecha_entrega_original": pd.Timestamp("2026-08-20"), "dias_diferencia_entrega": 5, "regla_aplicada": "Original Forward: adición Forward", "valor_base": 500_000, "acumulado_previo": 1_000_000, "tarifa_compra_aplicada": .004, "tarifa_compra_esperada": .003, "registro_compra_aplicado": 2_000, "registro_compra_esperado": 1_500, "diferencia_compra": 500, "resultado_registro_compra": "Alerta", "motivo_registro_compra": "Diferencia superior a tolerancia", "tarifa_venta_aplicada": .003, "tarifa_venta_esperada": .003, "registro_venta_aplicado": 1_500, "registro_venta_esperado": 1_500, "diferencia_venta": 0, "resultado_registro_venta": "Conforme", "motivo_registro_venta": "", "tarifa_cyl_compra_aplicada": .0021, "tarifa_cyl_compra_esperada": .0021, "cyl_compra_aplicado": 1_050, "cyl_compra_esperado": 1_050, "diferencia_cyl_compra": 0, "resultado_cyl_compra": "Conforme", "motivo_cyl_compra": "", "tarifa_cyl_venta_aplicada": .0021, "tarifa_cyl_venta_esperada": .0021, "cyl_venta_aplicado": 1_050, "cyl_venta_esperado": 1_050, "diferencia_cyl_venta": 0, "resultado_cyl_venta": "Conforme", "motivo_cyl_venta": "", "resultado_cyl": "Conforme", "diferencia_cyl": 0, "archivo_operacion": "operaciones.xlsx", "archivo_adicion": "adiciones.xlsx"},
        ])
        metricas = {codigo: {"population": 1, "alerts": 0, "not_evaluable": 0, "alert_difference_net": 0} for codigo in ["IND-01", "IND-02", "IND-03", "IND-04", "IND-05"]}
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            excel, pdf = raiz / "resultado_indicador.xlsx", raiz / "resultado_indicador.pdf"
            m.exportar_excel(excel, datos, {"periodo_evaluado": "2026-08", "tolerancia_cop": 1}, [], metricas)
            m.exportar_pdf(pdf, datos, {"periodo_evaluado": "2026-08", "tolerancia_cop": 1}, [])
            self.assertTrue(excel.exists() and excel.stat().st_size > 0)
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
            self.assertEqual(load_workbook(excel, read_only=True).sheetnames, ["Resumen", "IND_01", "IND_02", "IND_03", "IND_04", "IND_05"])


if __name__ == "__main__":
    unittest.main()
