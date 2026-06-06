import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"

VALID_IMPACTOS = {"bajo", "vecinal", "zonal"}
VALID_FORMATOS = {"EM-03", "EM-11", "EM-08"}

# Maps formato code back to impacto level for convenience
FORMATO_TO_IMPACTO = {
    "EM-03": "bajo",
    "EM-11": "vecinal",
    "EM-08": "zonal",
}


def load_tramites() -> Dict[str, Any]:
    path = DATA_DIR / "tramites.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="tramites.json not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get(
    "/tramites/formato/{formato}",
    summary="Instrucciones detalladas para un formato SIAPEM",
)
def get_tramites_por_formato(formato: str):
    """Returns detailed instructions for EM-03, EM-11, or EM-08."""
    # Normalise casing so em-03 works too
    formato = formato.upper()
    if formato not in VALID_FORMATOS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido. Valores permitidos: {', '.join(VALID_FORMATOS)}",
        )

    impacto = FORMATO_TO_IMPACTO[formato]
    data = load_tramites()
    fase3_detalle = data.get("fase3", {}).get(impacto)

    instrucciones = {
        "EM-03": {
            "nombre": "Aviso de Funcionamiento — Bajo Impacto",
            "descripcion": (
                "Aplica a establecimientos mercantiles de bajo impacto. "
                "El trámite es un simple aviso ante SIAPEM; no requiere pago "
                "y el acuse es inmediato tras el registro en línea."
            ),
            "requisitos": [
                "Identificación oficial del representante legal",
                "Comprobante de domicilio del local (máx. 3 meses)",
                "Certificado Único de Zonificación (CUS SEDUVI) vigente",
                "Clave Llave CDMX activa",
            ],
            "pasos": [
                "Ingresar a SIAPEM con tu cuenta Llave CDMX.",
                "Seleccionar 'Aviso de Funcionamiento EM-03 — Bajo Impacto'.",
                "Capturar datos del establecimiento (nombre, giro SCIAN, dirección, m²).",
                "Adjuntar documentos requeridos en formato PDF.",
                "Confirmar el aviso y descargar el acuse de recibo.",
            ],
        },
        "EM-11": {
            "nombre": "Aviso de Funcionamiento — Impacto Vecinal",
            "descripcion": (
                "Aplica a establecimientos mercantiles de impacto vecinal. "
                "Requiere pago de derechos (Art. 191 Fr. I CFCDMX) antes de "
                "que el aviso sea válido."
            ),
            "requisitos": [
                "Identificación oficial del representante legal",
                "Comprobante de domicilio del local (máx. 3 meses)",
                "Certificado Único de Zonificación (CUS SEDUVI) vigente",
                "Clave Llave CDMX activa",
                "Constancia de No Adeudo de Predial",
                "Constancia de No Adeudo de Agua (SACMEX)",
                "Comprobante de pago de derechos Art. 191 Fr. I CFCDMX",
            ],
            "pasos": [
                "Ingresar a SIAPEM con tu cuenta Llave CDMX.",
                "Seleccionar 'Aviso de Funcionamiento EM-11 — Impacto Vecinal'.",
                "Capturar datos del establecimiento.",
                "Realizar el pago de derechos en la Tesorería CDMX o en línea.",
                "Adjuntar documentos requeridos y comprobante de pago.",
                "Enviar la solicitud y esperar notificación de validación (1-3 días hábiles).",
                "Descargar el acuse validado.",
            ],
        },
        "EM-08": {
            "nombre": "Solicitud de Permiso — Impacto Zonal",
            "descripcion": (
                "IMPORTANTE: Es una Solicitud de PERMISO, no un aviso. "
                "Requiere autorización expresa de la Alcaldía y el plazo puede "
                "extenderse de 30 a 60 días hábiles. Sin permiso autorizado, "
                "el establecimiento NO puede operar."
            ),
            "requisitos": [
                "Identificación oficial del representante legal",
                "Escritura constitutiva o acta de nacimiento + CURP",
                "Comprobante de domicilio del local (máx. 3 meses)",
                "Certificado Único de Zonificación (CUS SEDUVI) vigente",
                "Clave Llave CDMX activa",
                "Constancia de No Adeudo de Predial",
                "Constancia de No Adeudo de Agua (SACMEX)",
                "Programa Interno de Protección Civil (si aplica)",
                "Dictamen de seguridad estructural (si aplica)",
                "Comprobante de pago de derechos Art. 191 Fr. II CFCDMX",
            ],
            "pasos": [
                "Ingresar a SIAPEM con tu cuenta Llave CDMX.",
                "Seleccionar 'Solicitud de Permiso EM-08 — Impacto Zonal'.",
                "Capturar datos completos del establecimiento y representante legal.",
                "Realizar el pago de derechos correspondiente.",
                "Adjuntar TODOS los documentos requeridos en formato PDF.",
                "Enviar la solicitud; la Alcaldía revisará en los plazos establecidos.",
                "Atender requerimientos de información adicional si la Alcaldía los solicita.",
                "Una vez autorizado, descargar el permiso firmado digitalmente.",
                "Exhibir el permiso físicamente en el establecimiento.",
            ],
            "advertencia": (
                "No inicies operaciones antes de recibir la autorización. "
                "Opera sin permiso puede resultar en clausura inmediata y multas "
                "conforme a la LEM."
            ),
        },
    }

    return {
        "formato": formato,
        "impacto": impacto,
        "instrucciones": instrucciones[formato],
        "siapem_detalle": fase3_detalle,
        "link_siapem": "https://siapem.cdmx.gob.mx/index.xhtml",
    }


@router.get(
    "/tramites/{impacto}",
    summary="Ruta de trámites para un nivel de impacto",
)
def get_tramites_por_impacto(impacto: str):
    """Returns the full tramite route (all phases) for bajo/vecinal/zonal."""
    impacto = impacto.lower()
    if impacto not in VALID_IMPACTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Impacto inválido. Valores permitidos: {', '.join(VALID_IMPACTOS)}",
        )

    data = load_tramites()

    # fase1 and fase2 apply to all impactos (filter by aplica_impactos field)
    fase1 = [
        step for step in data.get("fase1", [])
        if impacto in step.get("aplica_impactos", [])
    ]
    fase2 = [
        step for step in data.get("fase2", [])
        if impacto in step.get("aplica_impactos", [])
    ]
    fase3 = data.get("fase3", {}).get(impacto)

    return {
        "impacto": impacto,
        "fase1_prerequisitos": fase1,
        "fase2_documentos": fase2,
        "fase3_registro": fase3,
        "total_pasos": len(fase1) + len(fase2) + (1 if fase3 else 0),
    }
