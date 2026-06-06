import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fuzzywuzzy import fuzz, process

from api.models import ViabilidadRequest, ViabilidadResponse

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Helpers — data loaders
# ---------------------------------------------------------------------------

def _load_json(filename: str) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"{filename} not found in data/")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_giro(query: str, giros: list) -> Optional[dict]:
    """Return the best-matching giro for query using fuzzy matching."""
    if not giros:
        return None
    nombres = [g["nombre"] for g in giros]
    matches = process.extractOne(query, nombres, scorer=fuzz.token_set_ratio)
    if matches is None or matches[1] < 30:
        return None
    return next((g for g in giros if g["nombre"] == matches[0]), None)


def _resolve_alcaldia(alcaldia: str, alcaldias: dict) -> Optional[str]:
    """Return the canonical alcaldía key for the given string (case-insensitive)."""
    for key in alcaldias:
        if key.lower() == alcaldia.lower():
            return key
    for key in alcaldias:
        if alcaldia.lower() in key.lower() or key.lower() in alcaldia.lower():
            return key
    return None


def _resolve_colonia(colonia: str, colonias: dict) -> Optional[str]:
    if not colonia:
        return None
    for key in colonias:
        if key.lower() == colonia.lower():
            return key
    for key in colonias:
        if colonia.lower() in key.lower():
            return key
    return None


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def _calc_uso_suelo(zona_tipo: str, impacto: str) -> dict:
    """
    Determine uso de suelo compatibility.
    - habitacional zones are restrictive for zonal/vecinal impacto
    - comercial/mixto zones are more permissive
    """
    compatible = True
    advertencia = None

    if zona_tipo == "habitacional":
        if impacto == "zonal":
            compatible = False
            advertencia = (
                "Zona predominantemente habitacional. El impacto zonal es muy "
                "restrictivo en este tipo de zona; es probable que no sea compatible "
                "con el uso de suelo. Solicita el CUS SEDUVI para confirmar."
            )
        elif impacto == "vecinal":
            advertencia = (
                "Zona habitacional. Verifica con el CUS SEDUVI que el giro está "
                "permitido; en algunos casos se requiere dictamen adicional."
            )
    elif zona_tipo == "mixto":
        if impacto == "zonal":
            advertencia = (
                "Zona mixta. En general compatible, pero confirma con el CUS SEDUVI "
                "para establecimientos de impacto zonal."
            )
    # comercial zones are generally permissive for all impactos

    return {
        "zona_tipo": zona_tipo,
        "compatible": compatible,
        "advertencia": advertencia,
        "link_cus": "http://certificadodigital.cdmx.gob.mx:8080/CertificadoDigital/certificado/solicitaCertificado",
        "nota": "Verificación definitiva requiere CUS SEDUVI vigente.",
    }


def _calc_competencia(scian: str, competencia_data: dict, nivel_competencia_str: str) -> dict:
    scian_entry = competencia_data.get(scian, {
        "colonia_promedio": 3,
        "alcaldia_promedio": 40,
    })
    col_prom = scian_entry.get("colonia_promedio", 3)
    alc_prom = scian_entry.get("alcaldia_promedio", 40)

    nivel = "alto" if col_prom >= 5 else ("medio" if col_prom >= 3 else "bajo")

    recomendacion = {
        "bajo": "Baja competencia en la zona — buena oportunidad de mercado.",
        "medio": "Competencia moderada. Diferencia tu propuesta de valor.",
        "alto": "Alta saturación en la colonia. Considera una ubicación alternativa o nicho especializado.",
    }

    return {
        "competidores_estimados_colonia": col_prom,
        "competidores_estimados_alcaldia": alc_prom,
        "nivel_competencia": nivel,
        "recomendacion": recomendacion[nivel],
        "fuente": "DENUE simulado (referencia estadística)",
    }


def _calc_rentabilidad(renta_m2: int, m2: int, giro_nombre: str) -> dict:
    """
    Estimate basic revenue and profitability metrics.
    Assumptions (illustrative for hackathon):
      - Ticket promedio and visits/day depend on giro category
      - Revenue = ticket * visits/day * 30
      - Gross margin varies by giro type
    """
    # Simple heuristics by giro keyword
    giro_lower = giro_nombre.lower()

    if any(k in giro_lower for k in ["restaurante", "fonda", "café", "cafetería"]):
        ticket = 180
        visitas_dia = max(20, m2 // 4)
        margen_bruto = 0.62
    elif any(k in giro_lower for k in ["bar", "cantina", "antro", "discoteca", "cervecería"]):
        ticket = 300
        visitas_dia = max(15, m2 // 6)
        margen_bruto = 0.68
    elif any(k in giro_lower for k in ["tienda", "abarrotes", "farmacia", "papelería"]):
        ticket = 80
        visitas_dia = max(30, m2 // 3)
        margen_bruto = 0.28
    elif any(k in giro_lower for k in ["gimnasio", "salon", "cine", "club"]):
        ticket = 250
        visitas_dia = max(10, m2 // 8)
        margen_bruto = 0.55
    else:
        ticket = 150
        visitas_dia = max(15, m2 // 5)
        margen_bruto = 0.45

    ingreso_mensual = ticket * visitas_dia * 30
    ganancia_bruta = ingreso_mensual * margen_bruto

    return {
        "ticket_promedio_estimado": ticket,
        "visitas_dia_estimadas": visitas_dia,
        "ingreso_mensual_estimado": round(ingreso_mensual),
        "margen_bruto_pct": round(margen_bruto * 100),
        "ganancia_bruta_estimada": round(ganancia_bruta),
        "nota": "Estimaciones ilustrativas. Elabora tu propio flujo de caja.",
    }


def _calc_gastos_fijos(renta_m2: int, m2: int) -> dict:
    renta = renta_m2 * m2
    nomina_estimada = max(8_000, m2 * 25)      # rough: 1 employee per ~20m²
    servicios = max(2_000, m2 * 8)             # water, electricity, internet
    otros = round((renta + nomina_estimada + servicios) * 0.10)
    total = renta + nomina_estimada + servicios + otros

    return {
        "renta_local": renta,
        "nomina_estimada": nomina_estimada,
        "servicios": servicios,
        "otros_gastos": otros,
        "total_mensual": total,
        "nota": "Estimación referencial. Nómina asume salario mínimo CDMX.",
    }


def _calc_tramites(impacto: str, proteccion_civil: bool, tramites_data: dict) -> dict:
    fase1 = [
        step for step in tramites_data.get("fase1", [])
        if impacto in step.get("aplica_impactos", [])
    ]
    fase2 = [
        step for step in tramites_data.get("fase2", [])
        if impacto in step.get("aplica_impactos", [])
    ]

    # Filter out proteccion civil step if not required
    if not proteccion_civil:
        fase1 = [s for s in fase1 if s.get("clave") != "proteccion_civil"]

    fase3 = tramites_data.get("fase3", {}).get(impacto)
    total = len(fase1) + len(fase2) + (1 if fase3 else 0)

    plazo_map = {"bajo": "1-3 días", "vecinal": "5-10 días hábiles", "zonal": "30-60 días hábiles"}

    return {
        "impacto": impacto,
        "fase1_prerequisitos": fase1,
        "fase2_documentos": fase2,
        "fase3_registro": fase3,
        "total_pasos": total,
        "plazo_estimado": plazo_map.get(impacto, "variable"),
    }


def _load_programas_apoyo() -> List[dict]:
    """Return programas de apoyo. Loads from JSON if exists, else returns defaults."""
    path = DATA_DIR / "programas_apoyo.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # Fallback hardcoded programs (for demo when file doesn't exist yet)
    return [
        {
            "nombre": "Fondo para el Desarrollo Social (FONDESO)",
            "descripcion": "Financiamiento para micro y pequeñas empresas en CDMX.",
            "monto_maximo": "hasta $200,000 MXN",
            "link": "https://www.fondeso.cdmx.gob.mx/",
        },
        {
            "nombre": "Programa Capital Semilla SEDECO",
            "descripcion": "Apoyo a nuevos emprendedores con capital inicial y asesoría.",
            "monto_maximo": "hasta $50,000 MXN",
            "link": "https://www.sedeco.cdmx.gob.mx/",
        },
        {
            "nombre": "INADEM / Fondo PyME (SE Federal)",
            "descripcion": "Apoyos federales para micro y pequeñas empresas.",
            "monto_maximo": "variable",
            "link": "https://www.gob.mx/se/acciones-y-programas/fondo-pyme",
        },
        {
            "nombre": "Centros de Desarrollo Empresarial (CIDE CDMX)",
            "descripcion": "Asesoría gratuita en trámites, plan de negocios y financiamiento.",
            "monto_maximo": "Gratuito",
            "link": "https://www.sedeco.cdmx.gob.mx/servicios/servicio/centros-de-desarrollo-empresarial",
        },
    ]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/viabilidad",
    response_model=ViabilidadResponse,
    summary="Análisis completo de viabilidad para un negocio",
)
def post_viabilidad(req: ViabilidadRequest):
    """
    Full viability analysis:
    1. Resolve giro via fuzzy match
    2. Apply alcohol override (principal → zonal)
    3. Check uso de suelo compatibility
    4. Compute competencia
    5. Compute rentabilidad and gastos fijos from zona renta data
    6. Build tramites route
    7. Evaluate protección civil exemption
    8. Load programas de apoyo
    """
    giros = _load_json("giros.json")
    zonas = _load_json("zonas.json")
    tramites_data = _load_json("tramites.json")

    # 1. Resolve giro
    giro = _find_giro(req.giro, giros)
    if giro is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró un giro que coincida con '{req.giro}'. "
                   "Prueba con otro término.",
        )

    # 2. Apply alcohol rule: if alcohol=principal → force zonal
    impacto = giro.get("impacto", "bajo")
    formato_siapem = giro.get("formato_siapem", "EM-03")

    if req.alcohol == "principal":
        impacto = "zonal"
        formato_siapem = "EM-08"

    # 3. Resolve zona data
    alcaldias = zonas.get("alcaldias", {})
    alcaldia_key = _resolve_alcaldia(req.alcaldia, alcaldias)
    if alcaldia_key is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alcaldía '{req.alcaldia}' no encontrada.",
        )

    alcaldia_data = alcaldias[alcaldia_key]
    colonia_key = _resolve_colonia(req.colonia or "", alcaldia_data.get("colonias", {}))
    colonia_data = alcaldia_data["colonias"].get(colonia_key) if colonia_key else None

    # Pick the most specific renta_m2 available
    if colonia_data:
        renta_m2 = colonia_data.get("renta_m2", alcaldia_data.get("renta_m2", 220))
        zona_tipo = colonia_data.get("zona_tipo", alcaldia_data.get("zona_predominante", "mixto"))
    else:
        renta_m2 = alcaldia_data.get("renta_m2", zonas.get("renta_m2_promedio_cdmx", 220))
        zona_tipo = alcaldia_data.get("zona_predominante", "mixto")

    # 3. Uso de suelo compatibility
    uso_suelo = _calc_uso_suelo(zona_tipo, impacto)

    # 4. Competencia
    scian = giro.get("scian", "")
    competencia_data = zonas.get("competencia_por_scian", {})
    nivel_str = "medio"
    competencia = _calc_competencia(scian, competencia_data, nivel_str)

    # 5. Rentabilidad & gastos fijos
    rentabilidad = _calc_rentabilidad(renta_m2, req.m2, giro["nombre"])
    gastos_fijos = _calc_gastos_fijos(renta_m2, req.m2)

    # 7. Protección civil: exento if m2 <= 250 AND aforo < 100
    proteccion_civil_requerida = not (req.m2 <= 250 and req.aforo < 100)

    # 6. Tramites
    tramites = _calc_tramites(impacto, proteccion_civil_requerida, tramites_data)

    # 8. Programas de apoyo
    programas_apoyo = _load_programas_apoyo()

    # Links
    links = {
        "siapem": "https://siapem.cdmx.gob.mx/index.xhtml",
        "llave_cdmx": "https://llave.cdmx.gob.mx/",
        "cus_seduvi": "http://certificadodigital.cdmx.gob.mx:8080/CertificadoDigital/certificado/solicitaCertificado",
        "proteccion_civil": "https://www.proteccioncivil.cdmx.gob.mx/",
        "fondeso": "https://www.fondeso.cdmx.gob.mx/",
        "sedeco": "https://www.sedeco.cdmx.gob.mx/",
        "retys": "https://retys.cdmx.gob.mx/",
    }

    return ViabilidadResponse(
        impacto=impacto,
        formato_siapem=formato_siapem,
        proteccion_civil_requerida=proteccion_civil_requerida,
        uso_suelo=uso_suelo,
        competencia=competencia,
        rentabilidad=rentabilidad,
        gastos_fijos=gastos_fijos,
        tramites=tramites,
        programas_apoyo=programas_apoyo,
        links=links,
    )
