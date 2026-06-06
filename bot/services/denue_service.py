"""
Servicio de consulta DENUE (Directorio Estadístico Nacional de Unidades Económicas).
Busca y analiza la competencia comercial en una zona.
"""
import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _nivel_competencia(count: int, umbral_baja: int = 3, umbral_alta: int = 8) -> str:
    """Determina el nivel textual de competencia según el conteo."""
    if count <= umbral_baja:
        return "baja"
    elif count <= umbral_alta:
        return "moderada"
    else:
        return "alta"


def _buscar_en_csv(scian: str, alcaldia: str, colonia: str = None) -> dict:
    """
    Intenta buscar competidores en el archivo CSV del DENUE.
    Retorna None si el archivo no existe o hay error.
    """
    csv_path = DATA_DIR / "denue_cdmx.csv"
    if not csv_path.exists():
        return None

    try:
        colonia_count = 0
        alcaldia_count = 0

        # El SCIAN puede ser de 6 dígitos; buscar prefijo de 4 dígitos para más resultados
        scian_prefix = scian[:4] if len(scian) >= 4 else scian
        alcaldia_lower = alcaldia.lower().strip()
        colonia_lower = colonia.lower().strip() if colonia else None

        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Buscar columnas relevantes (los nombres varían según versión del DENUE)
                scian_col = (
                    row.get("codigo_actividad_scian", "") or
                    row.get("CODIGO_ACTIVIDAD_SCIAN", "") or
                    row.get("scian", "")
                )
                mun_col = (
                    row.get("municipio", "") or
                    row.get("MUNICIPIO", "") or
                    row.get("nom_mun", "")
                ).lower()
                col_col = (
                    row.get("colonia", "") or
                    row.get("COLONIA", "") or
                    row.get("nom_col", "")
                ).lower()

                if scian_col.startswith(scian_prefix):
                    if alcaldia_lower in mun_col:
                        alcaldia_count += 1
                        if colonia_lower and colonia_lower in col_col:
                            colonia_count += 1

        return {
            "colonia_count": colonia_count,
            "alcaldia_count": alcaldia_count,
            "fuente": "DENUE CSV"
        }

    except Exception as e:
        logger.error(f"Error al leer denue_cdmx.csv: {e}")
        return None


def _buscar_en_zonas_json(scian: str, alcaldia: str, colonia: str = None) -> dict:
    """
    Usa datos de zonas.json como fallback cuando no hay CSV del DENUE.
    """
    try:
        with open(DATA_DIR / "zonas.json", encoding="utf-8") as f:
            zonas = json.load(f)
    except Exception as e:
        logger.error(f"Error al leer zonas.json para competencia: {e}")
        return {
            "colonia_count": 0,
            "alcaldia_count": 0,
            "fuente": "Sin datos"
        }

    competencia_db = zonas.get("competencia_por_scian", {})

    # Buscar por SCIAN o por prefijo de 4 dígitos
    scian_data = None
    if scian in competencia_db:
        scian_data = competencia_db[scian]
    else:
        # Intentar prefijo de 6 dígitos
        for key in competencia_db:
            if key.startswith(scian[:4]):
                scian_data = competencia_db[key]
                break

    if scian_data is None:
        # Si no hay datos específicos, usar promedios genéricos
        scian_data = {"colonia_promedio": 4, "alcaldia_promedio": 50}

    # Ajustar según la alcaldía (zonas más grandes tienen más competencia)
    alcaldias_grandes = ["Cuauhtémoc", "Gustavo A. Madero", "Iztapalapa", "Benito Juárez"]
    alcaldias_medianas = ["Miguel Hidalgo", "Álvaro Obregón", "Coyoacán", "Venustiano Carranza"]
    multiplicador = 1.0

    alcaldia_clean = alcaldia.strip()
    if any(a.lower() in alcaldia_clean.lower() for a in alcaldias_grandes):
        multiplicador = 1.4
    elif any(a.lower() in alcaldia_clean.lower() for a in alcaldias_medianas):
        multiplicador = 1.1

    colonia_count = max(1, int(scian_data["colonia_promedio"] * multiplicador))
    alcaldia_count = max(5, int(scian_data["alcaldia_promedio"] * multiplicador))

    return {
        "colonia_count": colonia_count,
        "alcaldia_count": alcaldia_count,
        "fuente": "Estimación (zonas.json)"
    }


def buscar_competencia(scian: str, alcaldia: str, colonia: str = None) -> dict:
    """
    Busca el nivel de competencia para un giro en una zona geográfica.

    Primero intenta cargar datos reales del CSV de DENUE.
    Si no existe el archivo, usa zonas.json como fallback.

    Args:
        scian: Código SCIAN del giro (ej. "722511" para restaurantes)
        alcaldia: Nombre de la alcaldía (ej. "Cuauhtémoc")
        colonia: Nombre de la colonia (opcional, ej. "Roma Norte")

    Returns:
        dict con: colonia_count (int), alcaldia_count (int), nivel (str), fuente (str)
    """
    # Intentar CSV primero
    resultado = _buscar_en_csv(scian, alcaldia, colonia)

    if resultado is None:
        # Fallback a zonas.json
        logger.info(f"DENUE CSV no disponible. Usando fallback para SCIAN {scian} en {alcaldia}.")
        resultado = _buscar_en_zonas_json(scian, alcaldia, colonia)

    colonia_count = resultado.get("colonia_count", 0)
    alcaldia_count = resultado.get("alcaldia_count", 0)

    # Determinar nivel de competencia basado en la colonia
    # (si no hay colonia, usar conteo de alcaldía normalizado)
    if colonia and colonia_count > 0:
        nivel = _nivel_competencia(colonia_count, umbral_baja=3, umbral_alta=7)
    else:
        # Normalizar alcaldía: dividir entre ~50 colonias promedio
        count_normalizado = alcaldia_count // 50
        nivel = _nivel_competencia(count_normalizado, umbral_baja=2, umbral_alta=5)

    return {
        "colonia_count": colonia_count,
        "alcaldia_count": alcaldia_count,
        "nivel": nivel,
        "fuente": resultado.get("fuente", "Desconocida")
    }
