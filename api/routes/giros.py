import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query
from fuzzywuzzy import fuzz, process

from api.models import GiroBusquedaResponse

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_giros() -> list:
    path = DATA_DIR / "giros.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="giros.json not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/giros", summary="Lista todos los giros disponibles")
def get_giros():
    """Returns all giros from data/giros.json."""
    return load_giros()


@router.get(
    "/giros/buscar",
    response_model=List[GiroBusquedaResponse],
    summary="Búsqueda difusa de giros por nombre",
)
def buscar_giros(q: str = Query(..., min_length=1, description="Término de búsqueda")):
    """Fuzzy-searches giros by name, returning the top 5 matches."""
    giros = load_giros()
    if not giros:
        return []

    nombres = [g["nombre"] for g in giros]

    # fuzzywuzzy process.extract returns (match, score, index) for list inputs
    matches = process.extract(q, nombres, scorer=fuzz.token_set_ratio, limit=5)

    results = []
    for match_nombre, score, _ in matches:
        if score < 30:
            # Skip very poor matches
            continue
        giro = next((g for g in giros if g["nombre"] == match_nombre), None)
        if giro:
            results.append(
                GiroBusquedaResponse(
                    nombre=giro["nombre"],
                    scian=giro.get("scian", ""),
                    impacto=giro.get("impacto", ""),
                    formato_siapem=giro.get("formato_siapem", ""),
                )
            )
    return results
