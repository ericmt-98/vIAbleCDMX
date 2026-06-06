import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_zonas() -> dict:
    path = DATA_DIR / "zonas.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="zonas.json not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/zonas", summary="Lista todas las alcaldías y colonias")
def get_zonas():
    """Returns all alcaldias and colonias from data/zonas.json."""
    data = load_zonas()
    alcaldias = data.get("alcaldias", {})

    result = []
    for nombre, info in alcaldias.items():
        result.append(
            {
                "alcaldia": nombre,
                "zona_predominante": info.get("zona_predominante"),
                "renta_m2": info.get("renta_m2"),
                "colonias": list(info.get("colonias", {}).keys()),
            }
        )
    return result


@router.get("/competencia", summary="Datos de competencia por giro y zona")
def get_competencia(
    scian: str = Query(..., description="Código SCIAN del giro"),
    alcaldia: str = Query(..., description="Nombre de la alcaldía"),
    colonia: Optional[str] = Query(None, description="Nombre de la colonia (opcional)"),
):
    """Returns competition data for a SCIAN code in a given zone."""
    data = load_zonas()
    alcaldias = data.get("alcaldias", {})
    competencia_por_scian = data.get("competencia_por_scian", {})

    # Look up the alcaldia (case-insensitive fuzzy match)
    alcaldia_key = None
    for key in alcaldias:
        if key.lower() == alcaldia.lower():
            alcaldia_key = key
            break

    if alcaldia_key is None:
        # Try partial match
        for key in alcaldias:
            if alcaldia.lower() in key.lower() or key.lower() in alcaldia.lower():
                alcaldia_key = key
                break

    if alcaldia_key is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alcaldía '{alcaldia}' no encontrada. Verifica el nombre.",
        )

    alcaldia_data = alcaldias[alcaldia_key]

    # Get SCIAN competition benchmarks
    scian_comp = competencia_por_scian.get(scian, {
        "colonia_promedio": 3,
        "alcaldia_promedio": 40,
    })

    # Determine colonia data
    colonia_data = None
    colonia_key = None
    if colonia:
        colonias = alcaldia_data.get("colonias", {})
        for key in colonias:
            if key.lower() == colonia.lower():
                colonia_key = key
                colonia_data = colonias[key]
                break
        if colonia_data is None:
            # Partial match
            for key, val in colonias.items():
                if colonia.lower() in key.lower():
                    colonia_key = key
                    colonia_data = val
                    break

    # Build response
    competidores_colonia = scian_comp.get("colonia_promedio", 3)
    competidores_alcaldia = scian_comp.get("alcaldia_promedio", 40)

    nivel_competencia = "alto" if competidores_colonia >= 5 else (
        "medio" if competidores_colonia >= 3 else "bajo"
    )

    return {
        "scian": scian,
        "alcaldia": alcaldia_key,
        "colonia": colonia_key,
        "competidores_estimados_colonia": competidores_colonia,
        "competidores_estimados_alcaldia": competidores_alcaldia,
        "nivel_competencia": nivel_competencia,
        "zona_tipo": (
            colonia_data.get("zona_tipo") if colonia_data
            else alcaldia_data.get("zona_predominante")
        ),
        "fuente": "DENUE simulado (datos de referencia)",
    }
