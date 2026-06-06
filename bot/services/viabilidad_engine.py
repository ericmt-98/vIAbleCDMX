"""
Motor de análisis de viabilidad comercial para ViableCDMX.
Implementa la lógica de negocio basada en la Ley de Establecimientos Mercantiles (LEM).
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _cargar_giros() -> list:
    """Carga el catálogo de giros comerciales desde el archivo JSON."""
    try:
        with open(DATA_DIR / "giros.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Archivo giros.json no encontrado. Usando datos de respaldo.")
        return [
            {"nombre": "Restaurante", "impacto": "vecinal", "formato_siapem": "EM-11",
             "articulo_lem": "Art. 19 LEM", "scian": "722511"},
            {"nombre": "Cafetería", "impacto": "bajo", "formato_siapem": "EM-03",
             "articulo_lem": "Art. 35 LEM", "scian": "722515"},
            {"nombre": "Tienda de Abarrotes", "impacto": "bajo", "formato_siapem": "EM-03",
             "articulo_lem": "Art. 35 LEM", "scian": "461110"},
            {"nombre": "Bar", "impacto": "zonal", "formato_siapem": "EM-08",
             "articulo_lem": "Art. 27 Bis LEM", "scian": "722412"},
        ]
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear giros.json: {e}")
        return []


def _cargar_zonas() -> dict:
    """Carga datos de zonas y rentas desde el archivo JSON."""
    try:
        with open(DATA_DIR / "zonas.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Archivo zonas.json no encontrado. Usando datos de respaldo.")
        return {
            "alcaldias": {},
            "renta_m2_promedio_cdmx": 220,
            "competencia_por_scian": {}
        }
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear zonas.json: {e}")
        return {"alcaldias": {}, "renta_m2_promedio_cdmx": 220, "competencia_por_scian": {}}


def clasificar_impacto(giro_nombre: str, vende_alcohol: str) -> dict:
    """
    Clasifica el impacto legal del negocio según la LEM.

    Args:
        giro_nombre: Nombre del giro comercial (se buscará por fuzzy match)
        vende_alcohol: "no", "complemento" o "principal"

    Returns:
        dict con: impacto, formato_siapem, articulo_lem, giro_nombre, scian
    """
    giros = _cargar_giros()

    if not giros:
        return {
            "impacto": "bajo",
            "formato_siapem": "EM-03",
            "articulo_lem": "Art. 35 LEM",
            "giro_nombre": giro_nombre,
            "scian": "000000"
        }

    # Intentar fuzzy match con fuzzywuzzy
    mejor_match = None
    mejor_score = 0

    try:
        from fuzzywuzzy import fuzz
        giro_lower = giro_nombre.lower().strip()
        for giro in giros:
            score = fuzz.partial_ratio(giro_lower, giro["nombre"].lower())
            if score > mejor_score:
                mejor_score = score
                mejor_match = giro
    except ImportError:
        logger.warning("fuzzywuzzy no disponible. Usando búsqueda exacta.")
        giro_lower = giro_nombre.lower().strip()
        for giro in giros:
            if giro_lower in giro["nombre"].lower() or giro["nombre"].lower() in giro_lower:
                mejor_match = giro
                break

    # Si no se encontró match, usar el primero como fallback
    if mejor_match is None:
        mejor_match = giros[0]
        logger.warning(f"No se encontró match para '{giro_nombre}', usando '{mejor_match['nombre']}'")

    impacto = mejor_match["impacto"]

    # Regla de negocio: si vende alcohol como giro principal y el impacto
    # no refleja esto, escalar a zonal
    if vende_alcohol == "principal" and impacto in ["bajo", "vecinal"]:
        logger.info(f"Escalando impacto de '{impacto}' a 'zonal' por venta de alcohol como giro principal.")
        impacto = "zonal"
        formato = "EM-08"
        articulo = "Art. 27 Bis LEM (Alcohol Principal)"
    else:
        formato = mejor_match["formato_siapem"]
        articulo = mejor_match["articulo_lem"]

    return {
        "impacto": impacto,
        "formato_siapem": formato,
        "articulo_lem": articulo,
        "giro_nombre": mejor_match["nombre"],
        "scian": mejor_match.get("scian", "000000")
    }


def evaluar_proteccion_civil(m2: int, aforo: int) -> dict:
    """
    Evalúa si el establecimiento requiere Programa Interno de Protección Civil.

    Regla: Art. 10, Apartado A, Fracción X, LEM:
    Exento si m2 <= 250 Y aforo < 100.

    Args:
        m2: Superficie del local en metros cuadrados
        aforo: Número máximo de personas

    Returns:
        dict con: requerido (bool), fundamento (str), accion (str)
    """
    exento = (m2 <= 250) and (aforo < 100)

    if exento:
        return {
            "requerido": False,
            "fundamento": "Art. 10, Ap. A, Fr. X, LEM - Exento (menor de 250 m² y menos de 100 personas)",
            "accion": "No necesitas presentar Programa Interno de Protección Civil."
        }
    else:
        razones = []
        if m2 > 250:
            razones.append(f"superficie mayor a 250 m² (tienes {m2} m²)")
        if aforo >= 100:
            razones.append(f"aforo de {aforo} o más personas")

        return {
            "requerido": True,
            "fundamento": f"Art. 10, Ap. A, Fr. X, LEM - Obligatorio por: {', '.join(razones)}",
            "accion": "Debes contratar empresa certificadora para elaborar tu Programa Interno de Protección Civil antes del registro SIAPEM."
        }


def validar_uso_suelo(giro_impacto: str, zona_tipo: str) -> dict:
    """
    Valida si el giro es compatible con el tipo de zonificación del uso de suelo.

    Matriz de compatibilidad basada en normativa SEDUVI:
    - bajo → habitacional = True (tiendas pequeñas compatibles en zonas residenciales)
    - vecinal → habitacional = False (restaurantes, salones: no en pura habitacional)
    - zonal → habitacional = False (bares, antros: incompatibles)
    - zonal → mixto = False (impacto zonal requiere zona comercial)

    Args:
        giro_impacto: "bajo", "vecinal" o "zonal"
        zona_tipo: "habitacional", "mixto" o "comercial"

    Returns:
        dict con: compatible (bool), zona_tipo (str), accion (str|None)
    """
    matriz = {
        "bajo": {
            "habitacional": True,
            "mixto": True,
            "comercial": True
        },
        "vecinal": {
            "habitacional": False,
            "mixto": True,
            "comercial": True
        },
        "zonal": {
            "habitacional": False,
            "mixto": False,
            "comercial": True
        }
    }

    impacto_key = giro_impacto.lower()
    zona_key = zona_tipo.lower()

    if impacto_key not in matriz:
        return {
            "compatible": True,
            "zona_tipo": zona_tipo,
            "accion": None
        }

    compatible = matriz[impacto_key].get(zona_key, False)

    if compatible:
        return {
            "compatible": True,
            "zona_tipo": zona_tipo,
            "accion": None
        }
    else:
        acciones = {
            ("vecinal", "habitacional"): (
                "Tu negocio de impacto vecinal NO es compatible con zona habitacional. "
                "Busca un local en zona mixta o comercial."
            ),
            ("zonal", "habitacional"): (
                "Tu negocio de impacto zonal NO es compatible con zona habitacional. "
                "Requieres zona comercial exclusivamente."
            ),
            ("zonal", "mixto"): (
                "Tu negocio de impacto zonal NO es compatible con zona mixta. "
                "Requieres zona comercial. Verifica con SEDUVI."
            ),
        }
        accion = acciones.get(
            (impacto_key, zona_key),
            f"Giro de impacto {giro_impacto} no compatible con zona {zona_tipo}. Consulta SEDUVI o CENPROIN."
        )

        return {
            "compatible": False,
            "zona_tipo": zona_tipo,
            "accion": accion
        }


def calcular_radar_mvp(competencia_score: int, zona_data: dict, giro_impacto: str) -> dict:
    """
    Calcula métricas para el análisis de viabilidad del negocio.

    Args:
        competencia_score: Número de competidores directos en la zona (mayor = más competencia)
        zona_data: Datos de la zona (debe incluir renta_m2)
        giro_impacto: "bajo", "vecinal" o "zonal"

    Returns:
        dict con: competencia (0-100), rentabilidad (0-100), gastos_fijos (0-100), bloqueante (bool)
    """
    zonas = _cargar_zonas()
    renta_promedio_cdmx = zonas.get("renta_m2_promedio_cdmx", 220)
    renta_zona = zona_data.get("renta_m2", renta_promedio_cdmx)

    # --- Competencia (menor competencia = mejor score) ---
    # Normalizar: 0 competidores = 100 puntos, 10+ = 0 puntos
    competencia_raw = min(competencia_score, 15)
    competencia_invertida = max(0, int(100 - (competencia_raw / 15 * 100)))

    # --- Rentabilidad ---
    # Se basa en la relación renta/promedio CDMX
    # Renta menor al promedio = más rentable (gastos menores)
    ratio_renta = renta_zona / renta_promedio_cdmx if renta_promedio_cdmx > 0 else 1

    if ratio_renta <= 0.7:
        rentabilidad = 85  # Zona muy económica
    elif ratio_renta <= 1.0:
        rentabilidad = 70  # Zona por debajo del promedio
    elif ratio_renta <= 1.5:
        rentabilidad = 50  # Zona en el promedio
    elif ratio_renta <= 2.0:
        rentabilidad = 35  # Zona cara
    else:
        rentabilidad = 20  # Zona muy cara (ej. Polanco, Santa Fe)

    # Ajuste por impacto del giro (los giros zonales tienen mayor margen pero más trámites)
    if giro_impacto == "zonal":
        rentabilidad = min(100, rentabilidad + 10)
    elif giro_impacto == "bajo":
        rentabilidad = max(0, rentabilidad - 5)

    # --- Gastos Fijos (score inverso: menor renta = mejor score) ---
    if renta_zona <= 100:
        gastos_fijos = 85  # Gastos muy bajos
    elif renta_zona <= 200:
        gastos_fijos = 70  # Gastos moderados
    elif renta_zona <= 350:
        gastos_fijos = 50  # Gastos altos
    elif renta_zona <= 500:
        gastos_fijos = 30  # Gastos muy altos
    else:
        gastos_fijos = 15  # Gastos extremadamente altos

    # --- Bloqueante ---
    # El análisis es bloqueante si la competencia es muy alta Y los gastos son elevados
    bloqueante = (competencia_invertida < 25) and (gastos_fijos < 30)

    return {
        "competencia": competencia_invertida,
        "rentabilidad": rentabilidad,
        "gastos_fijos": gastos_fijos,
        "bloqueante": bloqueante
    }


def generar_reporte_viabilidad(session_data: dict) -> str:
    """
    Genera un reporte de viabilidad completo en español para Telegram.

    Args:
        session_data: dict con: giro, alcaldia, colonia, m2, aforo, alcohol,
                      impacto, formato, proteccion_civil, uso_suelo, radar

    Returns:
        Texto formateado para Telegram (sin markdown, con emojis)
    """
    giro = session_data.get("giro", "No especificado")
    alcaldia = session_data.get("alcaldia", "No especificada")
    colonia = session_data.get("colonia", "No especificada")
    m2 = session_data.get("m2", 0)
    aforo = session_data.get("aforo", 0)
    alcohol = session_data.get("alcohol", "no")
    impacto = session_data.get("impacto", "bajo")
    formato = session_data.get("formato", "EM-03")
    pc_data = session_data.get("proteccion_civil", {})
    uso_suelo = session_data.get("uso_suelo", {})
    radar = session_data.get("radar", {})
    giro_nombre_oficial = session_data.get("giro_nombre_oficial", giro)

    # Emoji de impacto
    impacto_emojis = {"bajo": "🟢", "vecinal": "🟡", "zonal": "🔴"}
    impacto_emoji = impacto_emojis.get(impacto, "⚪")

    # Alcohol texto
    alcohol_textos = {
        "no": "No vende alcohol",
        "complemento": "Vende alcohol como complemento a alimentos",
        "principal": "Venta de alcohol como giro principal"
    }
    alcohol_texto = alcohol_textos.get(alcohol, alcohol)

    # Protección civil
    pc_requerido = pc_data.get("requerido", False)
    pc_texto = "Exento ✅" if not pc_requerido else "Requerido ⚠️"

    # Uso de suelo
    suelo_compatible = uso_suelo.get("compatible", True)
    suelo_texto = "Compatible ✅" if suelo_compatible else "Incompatible ❌"
    zona_tipo = uso_suelo.get("zona_tipo", "No determinado")

    # Radar
    competencia_score = radar.get("competencia", 50)
    rentabilidad_score = radar.get("rentabilidad", 50)
    gastos_score = radar.get("gastos_fijos", 50)

    def barra_progreso(score: int) -> str:
        filled = int(score / 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty + f" {score}/100"

    # Construir reporte
    lineas = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "📊 REPORTE DE VIABILIDAD",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🏪 Negocio: {giro_nombre_oficial}",
        f"📍 Ubicación: {colonia}, {alcaldia}",
        f"📐 Superficie: {m2} m²  |  👥 Aforo: {aforo} personas",
        f"🍷 Alcohol: {alcohol_texto}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "⚖️ CLASIFICACION LEGAL (LEM)",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"{impacto_emoji} Impacto: {impacto.upper()}",
        f"📋 Formato SIAPEM: {formato}",
        f"📖 Base legal: {session_data.get('articulo_lem', 'LEM CDMX')}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "🗺️ USO DE SUELO",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Zona: {zona_tipo.title()}",
        f"Estado: {suelo_texto}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "🛡️ PROTECCION CIVIL",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Programa Interno: {pc_texto}",
        f"Base: {pc_data.get('fundamento', 'Art. 10, Ap. A, Fr. X, LEM')}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "📈 ANALISIS DE MERCADO",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Ventaja competitiva:  {barra_progreso(competencia_score)}",
        f"Rentabilidad estimada: {barra_progreso(rentabilidad_score)}",
        f"Nivel de gastos fijos: {barra_progreso(gastos_score)}",
        "",
    ]

    # Recomendaciones
    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lineas.append("💡 RECOMENDACIONES")
    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lineas.append("")

    recomendaciones = []

    if not suelo_compatible:
        recomendaciones.append(
            "❌ ALERTA: El uso de suelo no es compatible con tu giro. "
            "Busca una zona adecuada antes de invertir."
        )

    if pc_requerido:
        recomendaciones.append(
            "⚠️ Necesitas contratar una empresa certificadora para tu Programa "
            "de Protección Civil. Presupuesta entre $5,000 y $30,000 MXN."
        )

    if impacto == "zonal":
        recomendaciones.append(
            "🔴 Tu negocio es de IMPACTO ZONAL. Recuerda que necesitas "
            "autorización expresa de la Alcaldía. El proceso puede tardar 30-60 dias habiles."
        )

    if competencia_score < 40:
        recomendaciones.append(
            "🔥 Alta competencia en tu zona. Considera diferenciarte o buscar "
            "otra colonia con menor saturacion del mercado."
        )

    if rentabilidad_score > 70:
        recomendaciones.append(
            "✅ La relacion costo-beneficio de la zona es favorable para tu giro."
        )
    elif rentabilidad_score < 40:
        recomendaciones.append(
            "⚠️ La renta en esta zona puede afectar tu rentabilidad. "
            "Analiza bien tus costos fijos antes de comprometerte."
        )

    if alcohol == "complemento" and impacto == "vecinal":
        recomendaciones.append(
            "ℹ️ La venta de alcohol como complemento mantiene tu clasificacion "
            "como Impacto Vecinal (EM-11). Si cambias el giro principal a alcohol, "
            "escalaras a Impacto Zonal (EM-08)."
        )

    if not recomendaciones:
        recomendaciones.append(
            "✅ Todo en orden. Procede con tu roadmap de tramites."
        )

    for rec in recomendaciones:
        lineas.append(rec)
        lineas.append("")

    lineas.append("━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lineas)
