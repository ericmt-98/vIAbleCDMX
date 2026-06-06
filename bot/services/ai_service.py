"""
Servicio de IA para ViableCDMX.
Usa Anthropic Claude para clasificar giros y responder preguntas sobre trámites.
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _cargar_lista_giros() -> list:
    """Carga nombres de giros desde giros.json."""
    try:
        with open(DATA_DIR / "giros.json", encoding="utf-8") as f:
            giros = json.load(f)
        return [g["nombre"] for g in giros]
    except Exception as e:
        logger.error(f"Error al cargar giros para AI: {e}")
        return [
            "Restaurante", "Cafetería", "Tienda de Abarrotes", "Estética",
            "Gimnasio", "Bar", "Hotel", "Salón de Fiestas", "Fonda",
            "Papelería", "Florería", "Cantina", "Discoteca"
        ]


def _get_anthropic_client():
    """Inicializa y devuelve el cliente de Anthropic."""
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY no configurada.")
            return None
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("Librería anthropic no instalada.")
        return None


def clasificar_giro_libre(texto: str) -> str:
    """
    Clasifica un texto libre de giro comercial al nombre oficial más cercano.

    Usa Claude claude-sonnet-4-6 para hacer la clasificación semántica.
    Si la API falla, devuelve el texto original.

    Args:
        texto: Descripción libre del negocio (ej. "quiero poner una taquería")

    Returns:
        Nombre oficial del giro más cercano del catálogo
    """
    client = _get_anthropic_client()
    if client is None:
        logger.info("Cliente Anthropic no disponible. Devolviendo texto original.")
        return texto.strip()

    lista_giros = _cargar_lista_giros()
    lista_str = ", ".join(lista_giros)

    try:
        mensaje = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            system=(
                "Eres un asistente que clasifica giros comerciales en CDMX. "
                "Dado un texto libre, devuelve ÚNICAMENTE el nombre del giro más cercano "
                f"de esta lista: {lista_str}. "
                "Solo devuelve el nombre exacto de la lista, sin explicación, "
                "sin punto final, sin comillas."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Clasifica este negocio: {texto}"
                }
            ]
        )

        giro_clasificado = mensaje.content[0].text.strip()

        # Verificar que la respuesta está en la lista
        giro_lower = giro_clasificado.lower()
        for nombre in lista_giros:
            if giro_lower == nombre.lower():
                return nombre

        # Si no coincide exactamente, hacer búsqueda parcial
        for nombre in lista_giros:
            if giro_lower in nombre.lower() or nombre.lower() in giro_lower:
                return nombre

        # Si aún no coincide, devolver la clasificación de Claude de todas formas
        return giro_clasificado

    except Exception as e:
        logger.error(f"Error al llamar a Anthropic API para clasificar giro: {e}")
        return texto.strip()


def responder_pregunta_tramite(pregunta: str) -> str:
    """
    Responde preguntas sobre trámites SIAPEM y la Ley de Establecimientos Mercantiles.

    Usa Claude con contexto especializado en la LEM y SIAPEM.
    Si la API falla, devuelve mensaje con instrucciones de contacto CENPROIN.

    Args:
        pregunta: Pregunta del usuario en lenguaje natural

    Returns:
        Respuesta en español con información sobre trámites
    """
    client = _get_anthropic_client()

    fallback_message = (
        "Lo siento, no puedo procesar tu pregunta en este momento.\n\n"
        "Para obtener ayuda personalizada, contacta al:\n\n"
        "🏢 Centro Promotor de Inversión (CENPROIN)\n"
        "📍 Av. Cuauhtémoc 899, Col. Narvarte, Alcaldía Benito Juárez\n"
        "🕐 Lunes a viernes, 9:00 a 14:30 horas\n"
        "📧 dudas.siapem@sedeco.cdmx.gob.mx\n"
        "🌐 siapem.cdmx.gob.mx"
    )

    if client is None:
        return fallback_message

    system_context = """Eres un asesor virtual especializado en la apertura de negocios en la
Ciudad de México. Tu conocimiento se basa en:

1. LEY DE ESTABLECIMIENTOS MERCANTILES (LEM CDMX):
   - Art. 35: Negocios de BAJO IMPACTO (estéticas, papelerías, abarrotes, cafeterías, fondas)
   - Art. 19: Negocios de IMPACTO VECINAL (restaurantes, hoteles, salones de fiestas, gimnasios)
   - Art. 27 Bis: Negocios de IMPACTO ZONAL (bares, cantinas, antros, casinos)
   - Art. 10, Ap. A, Fr. X: Exención de Protección Civil (< 250 m² Y < 100 personas)

2. SISTEMA SIAPEM (siapem.cdmx.gob.mx):
   - EM-03: Aviso de Funcionamiento para Bajo Impacto (gratuito, inmediato)
   - EM-11: Aviso de Funcionamiento para Impacto Vecinal (pago Art. 191 Fr. I)
   - EM-08: Solicitud de PERMISO para Impacto Zonal (pago Art. 191 Fr. II + autorización Alcaldía)

3. TRÁMITES PREVIOS:
   - Llave CDMX: obligatoria para cualquier trámite (llave.cdmx.gob.mx)
   - CUS SEDUVI: Certificado Único de Zonificación, vigencia 1 año
   - Constancias de no adeudo predial y agua: solo para Impacto Vecinal y Zonal
   - Programa Interno de Protección Civil: solo si > 250 m² o >= 100 personas

4. MIGRACIÓN SIAPEM:
   - Para usuarios con registro anterior: NO dar de alta como nuevo negocio
   - Usar "Dar de alta establecimiento con Clave Única"
   - Adjuntar trámites anteriores escaneados (EM-03, EM-B, EM-11, EM-A, EM-08)

5. CONTACTOS:
   - CENPROIN: Av. Cuauhtémoc 899, Narvarte, Benito Juárez. L-V 9:00-14:30
   - Email SIAPEM: dudas.siapem@sedeco.cdmx.gob.mx
   - SIAPEM: siapem.cdmx.gob.mx
   - CUS SEDUVI: certificadodigital.cdmx.gob.mx
   - No adeudos: data.finanzas.cdmx.gob.mx/formato_lc

Responde SIEMPRE en español. Sé conciso y claro. Usa emojis para hacer el texto más legible
en Telegram. NO uses Markdown con asteriscos o guiones bajos. Usa texto plano con emojis."""

    try:
        mensaje = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=system_context,
            messages=[
                {
                    "role": "user",
                    "content": pregunta
                }
            ]
        )

        return mensaje.content[0].text.strip()

    except Exception as e:
        logger.error(f"Error al llamar a Anthropic API para responder pregunta: {e}")
        return fallback_message
