# Whisper en su propio contenedor, lejos de Django.
#
# El servidor del IES tiene 2 vCPU, ~1,2 GB libres y NINGUNA swap: si algo se
# pasa de memoria, el kernel mata un contenedor cualquiera, y puede ser
# Postgres. Por eso esto vive aparte, con su propio tope en el compose: si
# Whisper se pasa, muere Whisper.
#
# `requests` no es opcional: sin él, faster-whisper no puede descargar el
# modelo (medido el 2026-09-24).
FROM python:3.12-slim

RUN pip install --no-cache-dir faster-whisper==1.1.1 requests

COPY servidor.py /servidor.py

ENV WHISPER_MODELO=small \
    WHISPER_DIR=/modelos \
    PYTHONUNBUFFERED=1

EXPOSE 9000
CMD ["python", "/servidor.py"]
