"""Transcribe notas de voz de clase. Un solo hilo, una petición cada vez.

POST /transcribir con los bytes del audio en el cuerpo → {"texto": "..."}.
GET  /salud → {"ok": true}.

Tres decisiones, las tres por la memoria del servidor del IES (2 vCPU, ~1,2 GB
libres, sin swap):

- **Un solo hilo** (`HTTPServer`, no `ThreadingHTTPServer`). Si llegan dos
  notas a la vez, la segunda espera. Dos transcripciones en paralelo doblarían
  la memoria.
- **Cada nota se transcribe en un proceso hijo que muere al acabar.** `small`
  cargado ocupa ~620 MB; tenerlo siempre en memoria se come la mitad de lo
  libre para usarlo unos segundos al día. Soltarlo con `del` + `gc.collect()`
  NO basta: medido el 2026-09-25, el proceso se quedaba con 633 MB en reposo y
  el pico de la segunda nota llegó a 846 MB, rozando el tope de 900. Un proceso
  que termina devuelve toda su memoria al sistema. Cuesta ~3 s por nota.
- **Al arrancar solo se DESCARGA el modelo**, sin cargarlo, para que la primera
  nota no espere a bajar ~480 MB.

Medido con la voz real de Jesús en clase (2026-09-25): `small` con un hilo,
~10 s por nota de 20 s, 620 MB de pico.
"""

import json
import multiprocessing
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

MODELO = os.environ.get("WHISPER_MODELO", "small")
DIR = os.environ.get("WHISPER_DIR", "/modelos")
LIMITE = 25 * 1024 * 1024  # algo por encima de los 20 MB que acepta Django

# Un texto de ejemplo con puntuación hace que Whisper puntúe. Sin él, `small`
# devolvió la nota de Jesús entera en minúsculas y sin un punto.
PROMPT = os.environ.get(
    "WHISPER_PROMPT",
    "Nota de clase. En tercero, el ejercicio ha funcionado; el jueves hay que repetirlo.",
)


def _transcribir_aqui(ruta):
    """Corre DENTRO del proceso hijo."""
    from faster_whisper import WhisperModel

    modelo = WhisperModel(
        MODELO, device="cpu", compute_type="int8", cpu_threads=1, download_root=DIR
    )
    segmentos, _ = modelo.transcribe(ruta, language="es", initial_prompt=PROMPT or None)
    return " ".join(s.text.strip() for s in segmentos).strip()


def transcribir(ruta):
    # `spawn`, no `fork`: el hijo arranca limpio y no hereda nada del padre.
    contexto = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=contexto) as hijo:
        return hijo.submit(_transcribir_aqui, ruta).result(timeout=300)


class Manejador(BaseHTTPRequestHandler):
    def _responder(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/salud":
            self._responder(200, {"ok": True, "modelo": MODELO})
        else:
            self._responder(404, {"error": "no existe"})

    def do_POST(self):
        if self.path != "/transcribir":
            self._responder(404, {"error": "no existe"})
            return
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0:
            self._responder(400, {"error": "audio vacío"})
            return
        if largo > LIMITE:
            self._responder(413, {"error": "audio demasiado grande"})
            return
        datos = self.rfile.read(largo)
        # A disco y no en memoria: PyAV decodifica mejor desde un fichero, y
        # así el audio no se queda duplicado en RAM mientras se transcribe.
        with tempfile.NamedTemporaryFile(suffix=".audio") as f:
            f.write(datos)
            f.flush()
            del datos
            try:
                texto = transcribir(f.name)
            except Exception as e:  # el audio puede venir roto
                self._responder(422, {"error": f"no se pudo transcribir: {e}"})
                return
        self._responder(200, {"texto": texto})

    def log_message(self, formato, *args):
        # Una línea por petición, sin la IP de quien llama.
        print(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}")


def descargar():
    from faster_whisper.utils import download_model

    download_model(MODELO, cache_dir=DIR)
    print(f"Modelo {MODELO} listo en {DIR}")


if __name__ == "__main__":
    descargar()
    HTTPServer(("0.0.0.0", 9000), Manejador).serve_forever()
