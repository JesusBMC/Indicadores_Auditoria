"""Diagnóstico de solo lectura para la verificación de referencia.

Ejecuta sin cambios el test_exportaciones.py de la copia de referencia, pero
ignora únicamente los errores de limpieza de tempfile.TemporaryDirectory. Sirve
para saber si las aserciones de test_excel_y_pdf pasan. No es el resultado
oficial de la prueba.
"""
import sys
import tempfile
import unittest
from pathlib import Path

REF = Path(r"c:\Users\jparrap\Proyectos-BMC\Indicadores_Auditoria\Indicador_01_Tarifas_MCP\.agents\verificacion\referencia_original")
sys.path.insert(0, str(REF / "pruebas"))

_TemporaryDirectory = tempfile.TemporaryDirectory


class _TemporaryDirectoryTolerante(_TemporaryDirectory):
    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False, delete=True):
        super().__init__(suffix=suffix, prefix=prefix, dir=dir, ignore_cleanup_errors=True)


tempfile.TemporaryDirectory = _TemporaryDirectoryTolerante

import test_exportaciones  # noqa: E402

suite = unittest.defaultTestLoader.loadTestsFromModule(test_exportaciones)
resultado = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if resultado.wasSuccessful() else 1)
