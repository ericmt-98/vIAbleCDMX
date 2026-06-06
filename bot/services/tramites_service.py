"""
Servicio de trámites para ViableCDMX.
Genera roadmaps y checklists de trámites según el tipo de negocio.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _cargar_tramites() -> dict:
    """Carga el catálogo de trámites desde el archivo JSON."""
    try:
        with open(DATA_DIR / "tramites.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Archivo tramites.json no encontrado. Usando datos de respaldo.")
        return _tramites_fallback()
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear tramites.json: {e}")
        return _tramites_fallback()


def _tramites_fallback() -> dict:
    """Datos de respaldo si no existe el archivo de trámites."""
    return {
        "fase1": [
            {
                "paso": 1, "clave": "llave_cdmx",
                "descripcion": "Cuenta Llave CDMX",
                "link": "https://llave.cdmx.gob.mx/",
                "costo": "Gratuito", "plazo": "Inmediato",
                "obligatorio": True
            },
            {
                "paso": 2, "clave": "cus_seduvi",
                "descripcion": "Certificado Único de Zonificación (CUS SEDUVI)",
                "link": "http://certificadodigital.cdmx.gob.mx:8080/CertificadoDigital/certificado/solicitaCertificado",
                "costo": "Variable", "plazo": "3-5 días hábiles",
                "obligatorio": True
            }
        ],
        "fase2": [
            {
                "paso": 4, "clave": "no_adeudo_predial",
                "descripcion": "Constancia de No Adeudo de Predial",
                "link": "https://data.finanzas.cdmx.gob.mx/formato_lc",
                "costo": "Gratuito", "plazo": "1-2 días hábiles",
                "obligatorio": True
            }
        ],
        "fase3": {
            "bajo": {
                "paso": 6, "formato": "EM-03",
                "descripcion": "EM-03 Aviso de Funcionamiento Bajo Impacto",
                "link": "https://siapem.cdmx.gob.mx/",
                "costo": "Gratuito", "plazo": "Inmediato"
            },
            "vecinal": {
                "paso": 6, "formato": "EM-11",
                "descripcion": "EM-11 Aviso de Funcionamiento Impacto Vecinal",
                "link": "https://siapem.cdmx.gob.mx/",
                "costo": "Pago derechos Art. 191 Fr. I", "plazo": "1-3 días"
            },
            "zonal": {
                "paso": 6, "formato": "EM-08",
                "descripcion": "EM-08 Solicitud de Permiso Impacto Zonal",
                "link": "https://siapem.cdmx.gob.mx/",
                "costo": "Pago derechos Art. 191 Fr. II", "plazo": "30-60 días"
            }
        }
    }


def generar_roadmap(impacto: str, proteccion_civil: bool) -> list:
    """
    Genera el roadmap ordenado de trámites según el tipo de impacto.

    Args:
        impacto: "bajo", "vecinal" o "zonal"
        proteccion_civil: True si se requiere Programa Interno de PC

    Returns:
        Lista de pasos ordenados con: paso, descripcion, link, costo, plazo, obligatorio
    """
    tramites = _cargar_tramites()
    roadmap = []

    # Fase 1: Trámites base (todos los negocios)
    fase1 = tramites.get("fase1", [])
    for tramite in fase1:
        aplica = tramite.get("aplica_impactos", ["bajo", "vecinal", "zonal"])
        if impacto in aplica:
            paso = {
                "paso": tramite["paso"],
                "descripcion": tramite["descripcion"],
                "detalle": tramite.get("detalle", ""),
                "link": tramite.get("link", ""),
                "costo": tramite.get("costo", "Variable"),
                "plazo": tramite.get("plazo", "Consultar"),
                "obligatorio": tramite.get("obligatorio", True),
                "fase": "Fase 1 - Documentos Base"
            }

            # Manejo especial para Protección Civil
            if tramite.get("clave") == "proteccion_civil":
                if not proteccion_civil:
                    paso["obligatorio"] = False
                    paso["descripcion"] = "Protección Civil (EXENTO)"
                    paso["detalle"] = "Tu negocio está exento por tener menos de 250 m² y menos de 100 personas."
                else:
                    paso["obligatorio"] = True

            roadmap.append(paso)

    # Fase 2: Pre-requisitos por impacto (solo vecinal/zonal)
    if impacto in ["vecinal", "zonal"]:
        fase2 = tramites.get("fase2", [])
        for tramite in fase2:
            aplica = tramite.get("aplica_impactos", ["vecinal", "zonal"])
            if impacto in aplica:
                roadmap.append({
                    "paso": tramite["paso"],
                    "descripcion": tramite["descripcion"],
                    "detalle": tramite.get("detalle", ""),
                    "link": tramite.get("link", ""),
                    "costo": tramite.get("costo", "Variable"),
                    "plazo": tramite.get("plazo", "Consultar"),
                    "obligatorio": tramite.get("obligatorio", True),
                    "fase": "Fase 2 - Pre-requisitos"
                })

    # Fase 3: Registro SIAPEM
    fase3 = tramites.get("fase3", {})
    siapem = fase3.get(impacto, fase3.get("bajo", {}))
    if siapem:
        roadmap.append({
            "paso": siapem.get("paso", 6),
            "descripcion": siapem.get("descripcion", f"Registro SIAPEM ({siapem.get('formato', 'EM-03')})"),
            "detalle": siapem.get("detalle", ""),
            "link": siapem.get("link", "https://siapem.cdmx.gob.mx/"),
            "costo": siapem.get("costo", "Gratuito"),
            "plazo": siapem.get("plazo", "Variable"),
            "obligatorio": True,
            "fase": "Fase 3 - Registro SIAPEM",
            "formato": siapem.get("formato", "EM-03")
        })

    return sorted(roadmap, key=lambda x: x["paso"])


def formatear_checklist(impacto: str, proteccion_civil: bool) -> str:
    """
    Formatea la lista de verificación como mensaje de Telegram.

    Args:
        impacto: "bajo", "vecinal" o "zonal"
        proteccion_civil: True si se requiere Programa Interno de PC

    Returns:
        Texto formateado con checkboxes para Telegram
    """
    impacto_nombres = {"bajo": "Bajo Impacto", "vecinal": "Impacto Vecinal", "zonal": "Impacto Zonal"}
    impacto_formatos = {"bajo": "EM-03", "vecinal": "EM-11", "zonal": "EM-08"}
    impacto_nombre = impacto_nombres.get(impacto, impacto.title())
    formato = impacto_formatos.get(impacto, "EM-03")

    lineas = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"✅ CHECKLIST FINAL - {impacto_nombre}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "Marca cada punto antes de ir al SIAPEM:",
        "",
        "📌 FASE 1 - DOCUMENTOS BASE",
        "",
        "☐ Cuenta Llave CDMX activa y funcionando",
        "   llave.cdmx.gob.mx",
        "",
        "☐ Certificado Unico de Zonificacion (CUS SEDUVI)",
        "   Vigencia maxima: 1 año",
        "   certificadodigital.cdmx.gob.mx",
        "",
    ]

    # Protección Civil
    if proteccion_civil:
        lineas.extend([
            "☐ Programa Interno de Proteccion Civil",
            "   Elaborado por empresa certificadora autorizada",
            "   proteccioncivil.cdmx.gob.mx",
            "",
        ])
    else:
        lineas.extend([
            "✅ Proteccion Civil - EXENTO",
            "   (menos de 250 m² Y menos de 100 personas)",
            "   Art. 10, Ap. A, Fr. X, LEM",
            "",
        ])

    # Fase 2 solo para vecinal y zonal
    if impacto in ["vecinal", "zonal"]:
        lineas.extend([
            "📌 FASE 2 - PRE-REQUISITOS ESPECIALES",
            "",
            "☐ Constancia de No Adeudo de Predial",
            "   Tramitar ante Tesoreria CDMX",
            "   data.finanzas.cdmx.gob.mx/formato_lc",
            "",
            "☐ Constancia de No Adeudo de Agua (SACMEX)",
            "   Tramitar ante SACMEX",
            "   data.finanzas.cdmx.gob.mx/formato_lc",
            "",
        ])

    # Fase 3: SIAPEM
    lineas.extend([
        "📌 FASE 3 - REGISTRO SIAPEM",
        "",
        f"☐ Ingresar a SIAPEM: siapem.cdmx.gob.mx",
        "☐ 'Mis negocios' → 'Dar de alta nuevo negocio'",
        "☐ Llenar datos de persona Fisica o Moral",
        "☐ 'Mis tramites' → 'Registrar nuevo tramite'",
        f"☐ Seleccionar formato {formato}",
        "☐ Registrar informacion solicitada",
    ])

    # Pago según impacto
    if impacto == "bajo":
        lineas.extend([
            "☐ Descargar e imprimir Acuse (SIN costo)",
            "",
        ])
    elif impacto == "vecinal":
        lineas.extend([
            "☐ Pagar linea de captura de derechos",
            "   (Art. 191, Fraccion I, Codigo Fiscal CDMX)",
            "☐ Descargar e imprimir Acuse",
            "",
        ])
    elif impacto == "zonal":
        lineas.extend([
            "☐ Pagar linea de captura de derechos",
            "   (Art. 191, Fraccion II, Codigo Fiscal CDMX)",
            "☐ Esperar autorizacion expresa de la Alcaldia",
            "   (Plazo estimado: 30-60 dias habiles)",
            "☐ Descargar e imprimir Acuse tras autorizacion",
            "",
        ])

    lineas.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "❓ Dudas: dudas.siapem@sedeco.cdmx.gob.mx",
        "🏢 CENPROIN: Av. Cuauhtemoc 899, Narvarte",
        "   Lunes a Viernes 9:00 - 14:30 hrs",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ])

    return "\n".join(lineas)


def get_formato_siapem_instrucciones(formato: str) -> str:
    """
    Devuelve instrucciones paso a paso para el registro en SIAPEM.

    Args:
        formato: "EM-03", "EM-11" o "EM-08"

    Returns:
        Texto formateado con instrucciones numeradas para Telegram
    """
    instrucciones = {
        "EM-03": {
            "titulo": "EM-03 - Aviso de Funcionamiento (Bajo Impacto)",
            "tipo": "Aviso de Funcionamiento",
            "costo": "GRATUITO - No requiere pago de derechos",
            "plazo": "Inmediato al completar el registro",
            "pasos": [
                "Entra a: siapem.cdmx.gob.mx",
                "Haz clic en 'Iniciar sesion' (esquina superior derecha)",
                "Accede con tu cuenta Llave CDMX",
                "Ve a 'Mis negocios' en el menu principal",
                "Selecciona 'Dar de alta nuevo negocio'",
                "Elige tipo de titular: Persona Fisica o Moral",
                "Llena todos los datos del negocio (nombre, domicilio, giro)",
                "Ve a 'Mis tramites' en el menu principal",
                "Selecciona 'Registrar nuevo tramite'",
                "Elige el negocio que acabas de registrar",
                "Selecciona el formato 'EM-03 - Funcionamiento de Bajo Impacto'",
                "Adjunta documentos: CUS SEDUVI vigente (y PC si aplica)",
                "Registra toda la informacion solicitada",
                "Haz clic en 'Descargar Acuse'",
                "Imprime tu Acuse - ya puedes operar legalmente"
            ],
            "documentos": [
                "Certificado Unico de Zonificacion (CUS SEDUVI) vigente (max. 1 año)",
                "Programa Interno de Proteccion Civil (solo si m² > 250 o aforo >= 100)"
            ],
            "nota": "Para Bajo Impacto el proceso es inmediato. El Acuse tiene validez legal desde el momento de descarga."
        },
        "EM-11": {
            "titulo": "EM-11 - Aviso de Funcionamiento (Impacto Vecinal)",
            "tipo": "Aviso de Funcionamiento",
            "costo": "Pago de derechos Art. 191, Fraccion I, Codigo Fiscal CDMX",
            "plazo": "1 a 3 dias habiles despues del pago",
            "pasos": [
                "Entra a: siapem.cdmx.gob.mx",
                "Accede con tu cuenta Llave CDMX",
                "Ve a 'Mis negocios'",
                "Selecciona 'Dar de alta nuevo negocio'",
                "Elige tipo de titular: Persona Fisica o Moral",
                "Llena los datos del negocio",
                "Ve a 'Mis tramites'",
                "Selecciona 'Registrar nuevo tramite'",
                "Elige tu negocio",
                "Selecciona 'EM-11 - Funcionamiento de Impacto Vecinal'",
                "Adjunta: CUS SEDUVI + Constancias de No Adeudo + PC (si aplica)",
                "Registra la informacion solicitada",
                "El sistema generara una linea de captura para pago",
                "Paga los derechos correspondientes (Art. 191 Fr. I CFCDMX)",
                "Una vez acreditado el pago, descarga e imprime tu Acuse"
            ],
            "documentos": [
                "Certificado Unico de Zonificacion (CUS SEDUVI) vigente",
                "Constancia de No Adeudo de Predial",
                "Constancia de No Adeudo de Agua (SACMEX)",
                "Programa Interno de Proteccion Civil (si aplica)"
            ],
            "nota": "Los negocios de Impacto Vecinal operan con Aviso, pero deben pagar derechos. A diferencia del Impacto Zonal, no requieren autorizacion de la Alcaldia."
        },
        "EM-08": {
            "titulo": "EM-08 - Solicitud de Permiso (Impacto Zonal)",
            "tipo": "SOLICITUD DE PERMISO (no es un Aviso)",
            "costo": "Pago de derechos Art. 191, Fraccion II, Codigo Fiscal CDMX",
            "plazo": "30 a 60 dias habiles (incluye autorizacion de la Alcaldia)",
            "pasos": [
                "Entra a: siapem.cdmx.gob.mx",
                "Accede con tu cuenta Llave CDMX",
                "Ve a 'Mis negocios'",
                "Selecciona 'Dar de alta nuevo negocio'",
                "Elige tipo de titular: Persona Fisica o Moral",
                "Llena los datos del negocio",
                "Ve a 'Mis tramites'",
                "Selecciona 'Registrar nuevo tramite'",
                "Elige tu negocio",
                "Selecciona 'EM-08 - Solicitud de Permiso Impacto Zonal'",
                "Adjunta: CUS SEDUVI + Constancias de No Adeudo + PC (si aplica)",
                "IMPORTANTE: Adjunta estudio de impacto si lo tienes",
                "Registra toda la informacion solicitada",
                "El sistema generara linea de captura para pago",
                "Paga los derechos (Art. 191 Fr. II CFCDMX)",
                "ESPERA: La Alcaldia revisara y autorizara (30-60 dias habiles)",
                "Recibiras notificacion de la resolucion",
                "Si es aprobado, descarga e imprime tu Permiso"
            ],
            "documentos": [
                "Certificado Unico de Zonificacion (CUS SEDUVI) vigente",
                "Constancia de No Adeudo de Predial",
                "Constancia de No Adeudo de Agua (SACMEX)",
                "Programa Interno de Proteccion Civil (si aplica)",
                "Estudio de Impacto Ambiental o Urbano (en algunos casos)"
            ],
            "nota": "ATENCION: Los establecimientos de Impacto Zonal NO pueden operar hasta recibir autorizacion expresa de la Alcaldia. Operar sin ella puede resultar en clausura y multas."
        }
    }

    datos = instrucciones.get(formato, instrucciones["EM-03"])

    lineas = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📋 {datos['titulo']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📄 Tipo: {datos['tipo']}",
        f"💰 Costo: {datos['costo']}",
        f"⏱ Plazo: {datos['plazo']}",
        "",
        "📝 PROCEDIMIENTO PASO A PASO:",
        "",
    ]

    for i, paso in enumerate(datos["pasos"], 1):
        lineas.append(f"{i}. {paso}")

    lineas.extend([
        "",
        "📎 DOCUMENTOS QUE NECESITAS:",
        "",
    ])

    for doc in datos["documentos"]:
        lineas.append(f"• {doc}")

    lineas.extend([
        "",
        f"ℹ️ NOTA IMPORTANTE:",
        datos["nota"],
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "🌐 siapem.cdmx.gob.mx",
        "📧 dudas.siapem@sedeco.cdmx.gob.mx",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ])

    return "\n".join(lineas)
