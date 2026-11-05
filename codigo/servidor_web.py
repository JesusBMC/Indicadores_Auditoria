"""Servidor local del Indicador 01 - Tarifas MCP.

Sirve la página, las corridas guardadas y un botón que calcula el mes elegido
usando el mismo código de cálculo que la línea de comandos. Escucha en todas
las interfaces (accesible desde otros PCs en la red local).

Uso:  python codigo\\servidor_web.py --raiz "."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

CODIGO = Path(__file__).resolve().parent
sys.path.insert(0, str(CODIGO))
import indicador_01_tarifas_mcp as motor  # noqa: E402

WEB = CODIGO / "web"
PATRON_CORRIDA = re.compile(r"^(\d{4}-(0[1-9]|1[0-2]))_(\d{8}_?\d{6})(_\d{1,3})?$")
PATRON_PERIODO = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
LIMITE_CUERPO = 1024
ARCHIVOS_REQUERIDOS = ("resultado.json", "metadatos_ejecucion.json", "dashboard.html")
ARCHIVOS_DESCARGABLES = {
    "dashboard.html": "text/html; charset=utf-8",
    "resultado_indicador.xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "resultado_indicador.pdf": "application/pdf",
    "resultado.json": "application/json; charset=utf-8",
    "metadatos_ejecucion.json": "application/json; charset=utf-8",
    "detalle_calculo.json": "application/json; charset=utf-8",
    "nota_auditoria_interna.txt": "text/plain; charset=utf-8",
    "codigo_utilizado.py": "text/plain; charset=utf-8",
}

# Estado de la única actualización permitida a la vez.
ESTADO = {"estado": "inactiva", "periodo": None, "inicio": None, "fin": None, "carpeta": None, "error": None}
BLOQUEO = threading.Lock()
CACHE_MESES: dict = {"meses": None}


# ---------- lectura de corridas y fuentes ----------

def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def corridas_validas(raiz: Path) -> list[dict]:
    """Carpetas de resultados completas, de la más reciente a la más antigua."""
    carpeta_resultados = raiz / "resultados"
    if not carpeta_resultados.is_dir():
        return []
    corridas = []
    for carpeta in carpeta_resultados.iterdir():
        if not carpeta.is_dir() or not PATRON_CORRIDA.match(carpeta.name):
            continue
        if any(not (carpeta / archivo).is_file() for archivo in ARCHIVOS_REQUERIDOS):
            continue
        try:
            resultado = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
            json.loads((carpeta / "metadatos_ejecucion.json").read_text(encoding="utf-8"))
            generado = datetime.fromisoformat(resultado["generated_at"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        corridas.append({"id": carpeta.name, "periodo": resultado.get("period"), "generado": generado, "resultado": resultado})
    corridas.sort(key=lambda corrida: (corrida["generado"], corrida["id"]), reverse=True)
    return corridas


def resumen(corrida: dict) -> dict:
    return {
        "id": corrida["id"],
        "periodo": corrida["periodo"],
        "generado": corrida["generado"].isoformat(timespec="seconds"),
        "version": corrida["resultado"].get("version"),
    }


def hash_archivo(ruta: Path) -> str:
    sha = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            sha.update(bloque)
    return sha.hexdigest()


def fuentes_actuales(raiz: Path) -> list[Path]:
    """Mismos archivos que registra cada corrida en metadatos_ejecucion.json."""
    fuentes: list[Path] = []
    for carpeta in ("operaciones", "adiciones", "parametros"):
        fuentes.extend(motor.archivos_xlsx(raiz / "fuentes" / carpeta))
    configuracion = raiz / "fuentes" / "parametros" / "configuracion_ejecucion.json"
    if configuracion.is_file():
        fuentes.append(configuracion)
    return fuentes


def fuentes_cambiadas(raiz: Path, ultima: dict | None) -> list[dict]:
    """Compara la huella actual de cada fuente con la de la última corrida válida."""
    if ultima is None:
        return []
    metadatos = json.loads((raiz / "resultados" / ultima["id"] / "metadatos_ejecucion.json").read_text(encoding="utf-8"))
    anteriores = {fuente["ruta"]: fuente["sha256"] for fuente in metadatos.get("fuentes", [])}
    actuales = {str(ruta.relative_to(raiz)): hash_archivo(ruta) for ruta in fuentes_actuales(raiz)}
    cambios = []
    for ruta, sha in actuales.items():
        if ruta not in anteriores:
            cambios.append({"archivo": ruta, "estado": "nuevo"})
        elif anteriores[ruta] != sha:
            cambios.append({"archivo": ruta, "estado": "cambiado"})
    for ruta in anteriores:
        if ruta not in actuales:
            cambios.append({"archivo": ruta, "estado": "faltante"})
    return cambios


def periodo_configurado(raiz: Path) -> str | None:
    try:
        return motor.cargar_configuracion(raiz)["periodo_evaluado"]
    except (OSError, ValueError, KeyError):
        return None


def obtener_meses(raiz: Path) -> list[str]:
    """Meses con operaciones. Se cachea hasta la siguiente actualización."""
    if CACHE_MESES["meses"] is None:
        CACHE_MESES["meses"] = motor.meses_con_operaciones(motor.cargar_datos(raiz))
    return CACHE_MESES["meses"]


def precalcular_meses(raiz: Path) -> None:
    """Lee las operaciones al arrancar, para que la primera carga de la página sea rápida."""
    try:
        meses = obtener_meses(raiz)
        print(f"Lista de meses lista: {len(meses)} meses con operaciones.", flush=True)
    except Exception as error:
        print(f"No se pudo leer la lista de meses: {error}", flush=True)


def seleccionado(meses: list[str], configurado: str | None) -> str | None:
    if configurado in meses:
        return configurado
    return meses[-1] if meses else None


def estado_completo(raiz: Path) -> dict:
    corridas = corridas_validas(raiz)
    ultima = corridas[0] if corridas else None
    try:
        cambios = fuentes_cambiadas(raiz, ultima)
    except (OSError, ValueError) as error:
        cambios = [{"archivo": "(no se pudo comparar)", "estado": str(error)}]
    return {
        "periodo_configurado": periodo_configurado(raiz),
        "ultima_corrida": resumen(ultima) if ultima else None,
        "fuentes_cambiadas": cambios,
        "actualizacion": dict(ESTADO),
    }


# ---------- cálculo en segundo plano ----------

def calcular(raiz: Path, periodo: str) -> None:
    try:
        datos = motor.cargar_datos(raiz)
        carpeta, _ = motor.ejecutar(raiz, periodo, datos)
        ESTADO.update(estado="completada", carpeta=carpeta.name, error=None)
    except Exception as error:  # el error se muestra en la página; la última válida no cambia
        traceback.print_exc()
        ESTADO.update(estado="fallida", error=str(error))
    finally:
        ESTADO["fin"] = ahora()
        CACHE_MESES["meses"] = None
        BLOQUEO.release()


# ---------- HTTP ----------

class Servidor(ThreadingHTTPServer):
    allow_reuse_address = False

    def __init__(self, direccion, manejador, raiz: Path, puerto: int):
        self.raiz = raiz
        self.puerto = puerto
        super().__init__(direccion, manejador)


class Manejador(BaseHTTPRequestHandler):
    server_version = "IndicadorLocal"

    def log_message(self, formato, *args):
        return  # sin registro de acceso en consola

    def do_GET(self):
        self._atender("GET")

    def do_POST(self):
        self._atender("POST")

    def _atender(self, metodo: str) -> None:
        try:
            ruta = urlsplit(self.path).path
            if metodo == "GET":
                return self._get(ruta)
            return self._post(ruta)
        except Exception:
            traceback.print_exc()
            return self._json(500, {"error": "error_interno", "mensaje": "Error interno. Revise la consola del servidor."})

    def _get(self, ruta: str) -> None:
        raiz = self.server.raiz
        if ruta == "/":
            return self._archivo(WEB / "index.html", "text/html; charset=utf-8")
        if ruta == "/app.js":
            return self._archivo(WEB / "app.js", "application/javascript; charset=utf-8")
        if ruta == "/api/estado":
            return self._json(200, estado_completo(raiz))
        if ruta == "/api/meses":
            try:
                meses = obtener_meses(raiz)
            except (OSError, ValueError, KeyError) as error:
                return self._json(422, {"error": "fuentes_no_disponibles", "mensaje": str(error)})
            return self._json(200, {"meses": meses, "seleccionado": seleccionado(meses, periodo_configurado(raiz))})
        if ruta == "/api/corridas":
            return self._json(200, {"corridas": [resumen(corrida) for corrida in corridas_validas(raiz)]})
        if ruta == "/api/corridas/ultima":
            corridas = corridas_validas(raiz)
            if not corridas:
                return self._json(404, {"error": "sin_corridas_validas", "mensaje": "Todavía no hay resultados. Elija un mes y pulse Actualizar datos."})
            corrida = corridas[0]
            return self._json(200, {
                **resumen(corrida),
                "resultado": corrida["resultado"],
                "dashboard": f"/api/corridas/{corrida['id']}/archivos/dashboard.html",
            })
        partes = ruta.split("/")
        if len(partes) == 6 and partes[1:3] == ["api", "corridas"] and partes[4] == "archivos":
            return self._descargar(unquote(partes[3]), unquote(partes[5]))
        return self._json(404, {"error": "ruta_no_encontrada", "mensaje": "Ruta no encontrada."})

    def _descargar(self, id_corrida: str, nombre: str) -> None:
        raiz = self.server.raiz
        if not PATRON_CORRIDA.match(id_corrida) or len(id_corrida) > 64:
            return self._json(400, {"error": "id_invalido", "mensaje": "Identificador de corrida no válido."})
        if nombre not in ARCHIVOS_DESCARGABLES:
            return self._json(404, {"error": "archivo_no_disponible", "mensaje": "Archivo no disponible."})
        if id_corrida not in {corrida["id"] for corrida in corridas_validas(raiz)}:
            return self._json(404, {"error": "corrida_no_encontrada", "mensaje": "La corrida no existe o está incompleta."})
        carpeta = (raiz / "resultados" / id_corrida).resolve()
        archivo = (carpeta / nombre).resolve()
        if archivo.parent != carpeta or not archivo.is_file():
            return self._json(404, {"error": "archivo_no_disponible", "mensaje": "Archivo no disponible."})
        if nombre == "dashboard.html":
            return self._archivo(archivo, ARCHIVOS_DESCARGABLES[nombre])
        return self._archivo(archivo, ARCHIVOS_DESCARGABLES[nombre], adjunto=True)

    def _post(self, ruta: str) -> None:
        if ruta != "/api/actualizar":
            return self._json(404, {"error": "ruta_no_encontrada", "mensaje": "Ruta no encontrada."})
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            return self._json(415, {"error": "tipo_no_soportado", "mensaje": "Envíe el cuerpo como application/json."})
        longitud = int(self.headers.get("Content-Length") or 0)
        if longitud > LIMITE_CUERPO:
            return self._json(413, {"error": "cuerpo_demasiado_grande", "mensaje": "Cuerpo demasiado grande."})
        crudo = self.rfile.read(longitud) if longitud else b""
        try:
            cuerpo = json.loads(crudo or b"{}")
        except ValueError:
            return self._json(400, {"error": "cuerpo_invalido", "mensaje": "El cuerpo no es JSON válido."})
        if not isinstance(cuerpo, dict) or set(cuerpo) - {"periodo"}:
            return self._json(400, {"error": "cuerpo_invalido", "mensaje": "Solo se admite la clave periodo."})
        raiz = self.server.raiz
        periodo = cuerpo.get("periodo") or periodo_configurado(raiz)
        if not isinstance(periodo, str) or not PATRON_PERIODO.match(periodo):
            return self._json(400, {"error": "periodo_invalido", "mensaje": "El mes debe tener el formato AAAA-MM."})
        try:
            meses = obtener_meses(raiz)
        except (OSError, ValueError, KeyError) as error:
            return self._json(422, {"error": "fuentes_no_disponibles", "mensaje": str(error)})
        if periodo not in meses:
            return self._json(422, {"error": "periodo_no_disponible", "mensaje": f"{periodo} no tiene operaciones cargadas."})
        if not BLOQUEO.acquire(blocking=False):
            return self._json(409, {"error": "actualizacion_en_curso", "mensaje": "Ya hay una actualización en curso."})
        ESTADO.update(estado="en_curso", periodo=periodo, inicio=ahora(), fin=None, carpeta=None, error=None)
        threading.Thread(target=calcular, args=(raiz, periodo), daemon=True).start()
        return self._json(202, {"estado": "en_curso", "periodo": periodo})

    def _json(self, estado: int, objeto: dict) -> None:
        cuerpo = json.dumps(objeto, ensure_ascii=False, default=str).encode("utf-8")
        self._enviar(estado, cuerpo, "application/json; charset=utf-8")

    def _archivo(self, ruta: Path, tipo: str, adjunto: bool = False) -> None:
        if not ruta.is_file():
            return self._json(404, {"error": "archivo_no_disponible", "mensaje": "Archivo no disponible."})
        extra = {"Content-Disposition": f'attachment; filename="{ruta.name}"'} if adjunto else None
        self._enviar(200, ruta.read_bytes(), tipo, extra)

    def _enviar(self, estado: int, cuerpo: bytes, tipo: str, extra: dict | None = None) -> None:
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for nombre, valor in (extra or {}).items():
            self.send_header(nombre, valor)
        self.end_headers()
        self.wfile.write(cuerpo)


def main() -> int:
    parser = argparse.ArgumentParser(description="Servidor local del Indicador 01 - Tarifas MCP")
    parser.add_argument("--raiz", type=Path, default=motor.raiz_predeterminada(), help="Carpeta que contiene fuentes\\ y resultados\\.")
    parser.add_argument("--puerto", type=int, default=8765, help="Puerto local, entre 1024 y 65535.")
    args = parser.parse_args()
    if not 1024 <= args.puerto <= 65535:
        print("ERROR: --puerto debe estar entre 1024 y 65535.", file=sys.stderr)
        return 2
    raiz = args.raiz.resolve()
    if not (raiz / "fuentes").is_dir():
        print(f"ERROR: no existe la carpeta fuentes en {raiz}", file=sys.stderr)
        return 1
    try:
        servidor = Servidor(("0.0.0.0", args.puerto), Manejador, raiz, args.puerto)
    except OSError:
        print(f"ERROR: el puerto {args.puerto} ya está en uso. Use --puerto con otro valor.", file=sys.stderr)
        return 1
    print(f"Indicador 01 en http://172.16.50.98:{args.puerto}/  (también accesible desde otros PCs en la red)", flush=True)
    print("Leyendo las operaciones para la lista de meses...", flush=True)
    threading.Thread(target=precalcular_meses, args=(raiz,), daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("Servidor detenido.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
