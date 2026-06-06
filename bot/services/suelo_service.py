"""
Servicio de verificación de Uso de Suelo para ViableCDMX.
Consulta zonas.json para determinar la compatibilidad del giro con la zonificación.
"""
import json
import logging
from pathlib import Path

from bot.services.viabilidad_engine import validar_uso_suelo

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Alcaldías conocidas en CDMX para normalización de nombres
ALCALDIAS_CDMX = [
    "Álvaro Obregón",
    "Azcapotzalco",
    "Benito Juárez",
    "Coyoacán",
    "Cuajimalpa",
    "Cuauhtémoc",
    "Gustavo A. Madero",
    "Iztacalco",
    "Iztapalapa",
    "La Magdalena Contreras",
    "Miguel Hidalgo",
    "Milpa Alta",
    "Tláhuac",
    "Tlalpan",
    "Venustiano Carranza",
    "Xochimilco",
]


def _cargar_zonas() -> dict:
    """Carga datos de zonas desde zonas.json."""
    try:
        with open(DATA_DIR / "zonas.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("zonas.json no encontrado.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear zonas.json: {e}")
        return {}


def _normalizar_alcaldia(alcaldia_input: str) -> str:
    """
    Intenta normalizar el nombre de la alcaldía haciendo coincidencia parcial.
    Devuelve el nombre oficial si se encuentra, o el texto original si no.
    """
    entrada = alcaldia_input.lower().strip()
    for nombre_oficial in ALCALDIAS_CDMX:
        if entrada in nombre_oficial.lower() or nombre_oficial.lower() in entrada:
            return nombre_oficial
    return alcaldia_input.strip()


def _obtener_zona_tipo(zonas_data: dict, alcaldia: str, colonia: str) -> tuple:
    """
    Obtiene el tipo de zona para una colonia específica.
    Devuelve (zona_tipo, renta_m2, fuente).
    """
    alcaldia_normal = _normalizar_alcaldia(alcaldia)

    # Intentar la estructura antigua: {alcaldias: {nombre: {colonias: {...}}}}
    alcaldias_data = zonas_data.get("alcaldias", zonas_data)

    # Buscar alcaldía
    datos_alcaldia = None
    for key in alcaldias_data:
        if key.lower() == alcaldia_normal.lower() or alcaldia_normal.lower() in key.lower():
            datos_alcaldia = alcaldias_data[key]
            break

    if datos_alcaldia is None:
        logger.info(f"Alcaldía '{alcaldia}' no encontrada en zonas.json.")
        return "mixto", 220, "Estimación (alcaldía no encontrada)"

    colonias_data = datos_alcaldia.get("colonias", {})
    colonia_lower = colonia.lower().strip() if colonia else ""

    # Buscar colonia exacta o parcial
    for nombre_col, datos_col in colonias_data.items():
        if colonia_lower and (
            colonia_lower in nombre_col.lower() or
            nombre_col.lower() in colonia_lower
        ):
            # Compatibilidad con ambas estructuras del JSON
            zona_tipo = (
                datos_col.get("zona_tipo") or
                datos_col.get("uso_suelo") or
                "mixto"
            )
            renta = datos_col.get("renta_m2", datos_alcaldia.get("renta_m2", 220))
            return zona_tipo, renta, f"zonas.json ({nombre_col})"

    # Si no se encontró la colonia, usar zona predominante de la alcaldía
    zona_predominante = (
        datos_alcaldia.get("zona_predominante") or
        "mixto"
    )
    renta_alcaldia = datos_alcaldia.get("renta_m2", 220)
    return zona_predominante, renta_alcaldia, f"Estimación (alcaldía {alcaldia_normal})"


def verificar_compatibilidad(alcaldia: str, colonia: str, impacto: str) -> dict:
    """
    Verifica si el giro es compatible con la zonificación de uso de suelo.

    Carga zonas.json para obtener el tipo de zona para la colonia especificada,
    luego usa viabilidad_engine.validar_uso_suelo() para verificar compatibilidad.

    Args:
        alcaldia: Nombre de la alcaldía (ej. "Cuauhtémoc")
        colonia: Nombre de la colonia (ej. "Roma Norte")
        impacto: Tipo de impacto del giro: "bajo", "vecinal" o "zonal"

    Returns:
        dict con: compatible (bool), zona_tipo (str), accion (str|None),
                  fuente (str), renta_m2 (int)
    """
    zonas_data = _cargar_zonas()

    zona_tipo, renta_m2, fuente = _obtener_zona_tipo(zonas_data, alcaldia, colonia)

    # Normalizar valores de zona_tipo
    zona_map = {
        "habitacional": "habitacional",
        "residencial": "habitacional",
        "mixto": "mixto",
        "comercial": "comercial",
        "industrial": "mixto",  # Para industrial, tratar como mixto
        "corredor_comercial": "comercial",
    }
    zona_tipo_normalizado = zona_map.get(zona_tipo.lower(), "mixto")

    # Validar compatibilidad usando el motor de viabilidad
    resultado = validar_uso_suelo(impacto, zona_tipo_normalizado)

    return {
        "compatible": resultado["compatible"],
        "zona_tipo": zona_tipo,
        "accion": resultado.get("accion"),
        "fuente": fuente,
        "renta_m2": renta_m2
    }
