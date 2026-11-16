# app/api/v1/endpoints/cognition.py
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.tables import MemoriaEpisodica, ReglaExtraccion
from app.services.cognition import (
    FEW_SHOT_THRESHOLD,
    MAX_EMAIL_CHARS,
    MAX_FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    CategoriaCorreo,
    CognitionService,
)

# ESTA ES LA LÍNEA QUE ARREGLA EL ERROR
router = APIRouter()

_CLASSIFICATION_FIELDS = (
    "categoria",
    "dependencia_emisora",
    "tipo_documento",
    "periodo",
    "nivel_confianza",
)

class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_EMAIL_CHARS)

class ExtractionRuleCreate(BaseModel):
    category: CategoriaCorreo
    subject_pattern: str | None = Field(default=None, max_length=255)
    sender_pattern: str | None = Field(default=None, max_length=255)
    instruction: str = Field(min_length=1, max_length=2000)

    @field_validator("subject_pattern", "sender_pattern")
    @classmethod
    def normalize_optional_pattern(cls, value):
        if value is None:
            return None
        return value.strip() or None

    @field_validator("instruction")
    @classmethod
    def require_instruction(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("La instrucción no puede estar vacía.")
        return value

def _classification_summary(value):
    if not isinstance(value, dict):
        return None
    return {field: value.get(field) for field in _CLASSIFICATION_FIELDS}

async def _ollama_status():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or not isinstance(
            payload.get("models", []), list
        ):
            raise ValueError("Ollama devolvió una lista de modelos inválida.")
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "connected": False,
            "error": str(exc),
            "chat_model_available": False,
            "embedding_model_available": False,
        }

    installed_models = {
        model.get("name")
        for model in payload["models"]
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    }

    def is_available(model_name):
        return model_name in installed_models or f"{model_name}:latest" in installed_models

    return {
        "connected": True,
        "error": None,
        "chat_model_available": is_available(settings.OLLAMA_CHAT_MODEL),
        "embedding_model_available": is_available(settings.OLLAMA_EMBEDDING_MODEL),
    }

@router.get("/diagnostics")
async def get_cognition_diagnostics(db: AsyncSession = Depends(get_db)):
    counts_result = await db.execute(
        select(
            func.count(MemoriaEpisodica.id),
            func.count(MemoriaEpisodica.id).filter(
                MemoriaEpisodica.correccion_usuario.is_not(None)
            ),
        )
    )
    total_memories, corrected_memories = counts_result.one()

    memories_result = await db.execute(
        select(MemoriaEpisodica)
        .order_by(MemoriaEpisodica.created_at.desc())
        .limit(25)
    )
    memories = memories_result.scalars().all()

    rules_result = await db.execute(
        select(ReglaExtraccion)
        .where(ReglaExtraccion.is_active.is_(True))
        .order_by(ReglaExtraccion.created_at.desc())
        .limit(100)
    )
    rules = rules_result.scalars().all()

    recent_memories = []
    for memory in memories:
        recent_memories.append(
            {
                "id": str(memory.id),
                "created_at": memory.created_at,
                "decision": _classification_summary(memory.decision_agente),
                "correction": _classification_summary(memory.correccion_usuario),
                "review_status": (
                    "sin retroalimentación"
                    if memory.correccion_usuario is None
                    else "correcta" if memory.fue_correcto else "corregida"
                ),
            }
        )

    return {
        "ollama": await _ollama_status(),
        "models": {
            "chat": settings.OLLAMA_CHAT_MODEL,
            "embedding": settings.OLLAMA_EMBEDDING_MODEL,
        },
        "classification": {
            "system_prompt": SYSTEM_PROMPT.strip(),
            "few_shot_threshold": FEW_SHOT_THRESHOLD,
            "max_similar_examples": MAX_FEW_SHOT_EXAMPLES,
            "max_email_chars": MAX_EMAIL_CHARS,
        },
        "memory": {
            "total": total_memories,
            "with_feedback": corrected_memories,
            "recent": recent_memories,
        },
        "active_rules": [
            {
                "category": rule.categoria,
                "subject_pattern": rule.patron_asunto,
                "sender_pattern": rule.patron_remitente,
                "instruction": rule.prompt_instruccion,
            }
            for rule in rules
        ],
    }

@router.post("/rules", status_code=201)
async def create_extraction_rule(
    request: ExtractionRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    rule = ReglaExtraccion(
        categoria=request.category.value,
        patron_asunto=request.subject_pattern,
        patron_remitente=request.sender_pattern,
        prompt_instruccion=request.instruction,
        is_active=True,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {
        "category": rule.categoria,
        "subject_pattern": rule.patron_asunto,
        "sender_pattern": rule.patron_remitente,
        "instruction": rule.prompt_instruccion,
        "is_active": rule.is_active,
    }

@router.post("/search")
async def search_similar_memories(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="La consulta no puede estar vacía.")

    cognition = CognitionService()
    try:
        embedding = await cognition.embed_text(request.query)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo generar el embedding con Ollama: {exc}",
        ) from exc

    matches = await cognition.find_similar_feedback(db, embedding, solo_corregidos=False, umbral=0.30)
    return {
        "query": request.query,
        "threshold": FEW_SHOT_THRESHOLD,
        "max_results": MAX_FEW_SHOT_EXAMPLES,
        "results": [
            {
                "memory_id": match["memory_id"],
                "similarity": match["similarity"],
                "created_at": match["created_at"],
                "was_correct": match["was_correct"],
                "classification": _classification_summary(match["label"]),
            }
            for match in matches
        ],
    }

# ==========================================
# RUTA PARA EL ANÁLISIS RAG (CEREBRO)
# ==========================================
class RagRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)

@router.post("/rag")
async def analyze_with_context(
    request: RagRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe una pregunta, busca contexto en la BD (RAG) y devuelve la respuesta del LLM.
    """
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="La consulta no puede estar vacía.")

    cognition = CognitionService()
    try:
        respuesta = await cognition.analizar_con_contexto(request.query, db)
        return {"respuesta": respuesta}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error durante el análisis cognitivo: {str(exc)}",
        )