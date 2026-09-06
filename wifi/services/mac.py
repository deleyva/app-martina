"""Normalización y validación de direcciones MAC.

La regla que da sentido a toda la app: una MAC *aleatoria* (la que iOS y Android
generan por red para no ser rastreados) tiene puesto el **bit localmente
administrado** — el bit 1 del primer octeto. Una MAC de fábrica, grabada por el
fabricante, lo tiene a cero. Eso permite rechazarla en el formulario en vez de
descubrirlo tres semanas después, cuando alguien no consigue conectarse.
"""

from __future__ import annotations

import re

# Formatos aceptados a la entrada: dos puntos, guiones, puntos (cisco), espacios
# o nada en absoluto.
_SEPARADORES = re.compile(r"[\s:.\-]+")
_HEX = set("0123456789ABCDEF")

MAC_NULA = "00:00:00:00:00:00"
MAC_DIFUSION = "FF:FF:FF:FF:FF:FF"

# Formatos de salida para pegar en el software de la red.
FORMATOS = {
    "colon": "AA:BB:CC:DD:EE:FF",
    "hyphen": "AA-BB-CC-DD-EE-FF",
    "plain": "AABBCCDDEEFF",
    "cisco": "AABB.CCDD.EEFF",
}


class MacInvalida(ValueError):
    """La cadena no es una MAC utilizable. El mensaje es apto para el usuario."""


def normalizar_mac(bruto: str) -> str:
    """Devuelve la MAC en forma canónica `AA:BB:CC:DD:EE:FF`.

    Acepta cualquiera de los formatos habituales. Lanza `MacInvalida` con un
    mensaje explicativo si no lo es.
    """
    limpio = _SEPARADORES.sub("", (bruto or "")).upper()

    if not limpio:
        msg = "Escribe la dirección MAC de tu dispositivo."
        raise MacInvalida(msg)

    if len(limpio) != 12 or any(c not in _HEX for c in limpio):
        msg = (
            "Esto no parece una dirección MAC. Tiene que tener 12 dígitos "
            "del 0 al 9 y de la A a la F, por ejemplo A4:83:E7:1C:90:2B."
        )
        raise MacInvalida(msg)

    return ":".join(limpio[i : i + 2] for i in range(0, 12, 2))


def primer_octeto(mac: str) -> int:
    return int(mac[:2], 16)


def es_aleatoria(mac: str) -> bool:
    """¿Tiene puesto el bit localmente administrado? Entonces no es de fábrica."""
    return bool(primer_octeto(mac) & 0b10)


def es_multicast(mac: str) -> bool:
    """El bit menos significativo del primer octeto marca tráfico multicast.

    Ningún dispositivo tiene una MAC así; si aparece, es que se ha copiado mal.
    """
    return bool(primer_octeto(mac) & 0b1)


def validar_mac(bruto: str) -> str:
    """Normaliza y rechaza todo lo que no sea una MAC física real."""
    mac = normalizar_mac(bruto)

    if mac in (MAC_NULA, MAC_DIFUSION):
        msg = "Esa no es la MAC de ningún dispositivo. Vuelve a mirarla."
        raise MacInvalida(msg)

    if es_multicast(mac):
        msg = (
            f"{mac} no puede ser la MAC de tu tarjeta WiFi: es una dirección de "
            "multidifusión. Comprueba que la has copiado entera y bien."
        )
        raise MacInvalida(msg)

    if es_aleatoria(mac):
        msg = (
            f"{mac} es una MAC aleatoria (privada), no la real de tu dispositivo. "
            "Es lo que ponen iOS y Android por defecto para cada red. "
            "Desactiva la dirección aleatoria en los ajustes de la red WiFi y "
            "vuelve a mirar la MAC — abajo tienes los pasos para tu sistema. "
            "Si no lo consigues, lo resolvemos presencialmente."
        )
        raise MacInvalida(msg)

    return mac


def formatear_mac(mac: str, formato: str = "colon") -> str:
    """Reescribe una MAC canónica en el formato que espera el otro software."""
    plano = mac.replace(":", "")
    if formato == "plain":
        return plano
    if formato == "hyphen":
        return "-".join(plano[i : i + 2] for i in range(0, 12, 2))
    if formato == "cisco":
        return ".".join(plano[i : i + 4] for i in range(0, 12, 4))
    return mac


def exportar(macs, formato: str = "colon", separador: str = "coma") -> str:
    """Construye el texto exacto que el administrativo pega en el otro software."""
    piezas = [formatear_mac(m, formato) for m in macs]
    if separador == "linea":
        return "\n".join(piezas)
    return ", ".join(piezas)
