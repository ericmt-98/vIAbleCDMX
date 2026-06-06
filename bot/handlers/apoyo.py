"""
Handler de programas de apoyo para ViableCDMX.
Muestra programas de financiamiento, crédito y asesoría disponibles.
"""
import json
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.states import APOYO, MENU

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _cargar_programas() -> list:
    """Carga los programas de apoyo desde el archivo JSON."""
    try:
        with open(DATA_DIR / "programas_apoyo.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("programas_apoyo.json no encontrado. Usando datos de respaldo.")
        return [
            {
                "nombre": "FONDESO - Fondo de Desarrollo Social CDMX",
                "descripcion": "Creditos para micro y pequeñas empresas.",
                "monto": "Desde $5,000 hasta $100,000 MXN",
                "link": "https://fondeso.cdmx.gob.mx/",
                "tipo": "Credito",
                "emoji": "💰"
            },
            {
                "nombre": "CENPROIN - Asesoria Gratuita",
                "descripcion": "Centro Promotor de Inversion. Asesoria personalizada gratuita.",
                "monto": "Gratuito",
                "link": "https://www.sedeco.cdmx.gob.mx/",
                "tipo": "Asesoria",
                "emoji": "🤝",
                "direccion": "Av. Cuauhtemoc 899, Narvarte, Benito Juarez",
                "horario": "Lunes a viernes, 9:00 a 14:30 hrs"
            }
        ]
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear programas_apoyo.json: {e}")
        return []


async def apoyo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Muestra la lista de programas de apoyo disponibles para emprendedores en CDMX.
    """
    query = update.callback_query
    if query:
        await query.answer()

    programas = _cargar_programas()

    lineas = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "💰 PROGRAMAS DE APOYO PARA EMPRENDEDORES CDMX",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "Aqui encontraras los principales apoyos disponibles:",
        "",
    ]

    for i, programa in enumerate(programas, 1):
        emoji = programa.get("emoji", "📌")
        nombre = programa.get("nombre", "Programa")
        descripcion = programa.get("descripcion", "")
        monto = programa.get("monto", "Variable")
        link = programa.get("link", "")
        tipo = programa.get("tipo", "")

        lineas.append(f"{i}. {emoji} {nombre}")
        if tipo:
            lineas.append(f"   Tipo: {tipo}")
        lineas.append(f"   {descripcion}")
        lineas.append(f"   Monto: {monto}")

        # Datos adicionales para CENPROIN
        if programa.get("direccion"):
            lineas.append(f"   Direccion: {programa['direccion']}")
        if programa.get("horario"):
            lineas.append(f"   Horario: {programa['horario']}")
        if programa.get("contacto"):
            lineas.append(f"   Contacto: {programa['contacto']}")

        if link:
            lineas.append(f"   Web: {link}")

        lineas.append("")

    lineas.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "💡 CONSEJO:",
        "Visita el CENPROIN para asesoria GRATUITA y personalizada",
        "sobre cual programa es mejor para tu caso.",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ])

    mensaje = "\n".join(lineas)

    botones = [
        [InlineKeyboardButton("← Volver al menu", callback_data="volver_menu")],
        [InlineKeyboardButton("🔍 Evaluar mi negocio", callback_data="menu_viabilidad")],
    ]
    teclado = InlineKeyboardMarkup(botones)

    if query:
        try:
            await query.edit_message_text(mensaje, reply_markup=teclado)
        except Exception:
            await query.message.reply_text(mensaje, reply_markup=teclado)
    else:
        await update.effective_message.reply_text(mensaje, reply_markup=teclado)

    return APOYO
