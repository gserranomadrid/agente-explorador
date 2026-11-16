import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine, get_db

logger = logging.getLogger(__name__)
_gmail_poll_task: asyncio.Task | None = None

async def _poll_gmail():
    from app.api.v1.endpoints.emails import sync_emails

    while True:
        await asyncio.sleep(settings.GMAIL_POLL_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as session:
                await sync_emails(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falló una ejecución del polling de Gmail.")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    global _gmail_poll_task
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text("ALTER TABLE correos ADD COLUMN IF NOT EXISTS clasificacion JSONB")
            )
            await conn.execute(
                text("ALTER TABLE memoria_episodica ADD COLUMN IF NOT EXISTS embedding vector")
            )
            for table, column in (
                ("memoria_episodica", "embedding"),
                ("documentos", "vector_embedding"),
            ):
                dimension_limit = await conn.execute(
                    text(
                        "SELECT atttypmod >= 0 FROM pg_attribute "
                        "WHERE attrelid = to_regclass(:table_name) "
                        "AND attname = :column_name AND NOT attisdropped"
                    ),
                    {"table_name": table, "column_name": column},
                )
                if dimension_limit.scalar_one_or_none():
                    await conn.execute(
                        text(
                            f"ALTER TABLE {table} ALTER COLUMN {column} "
                            f"TYPE vector USING {column}::vector"
                        )
                    )
    except Exception:
        logger.exception("No se pudo inicializar el esquema de base de datos.")
    else:
        if settings.GMAIL_POLL_INTERVAL_SECONDS > 0:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(
                        f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
                    )
                    response.raise_for_status()
                    available_models = {
                        item["name"] for item in response.json().get("models", [])
                    }
                required_models = {
                    settings.OLLAMA_CHAT_MODEL,
                    settings.OLLAMA_EMBEDDING_MODEL,
                }
                missing_models = {
                    model
                    for model in required_models
                    if model not in available_models
                    and f"{model}:latest" not in available_models
                }
                if missing_models:
                    logger.warning(
                        "Polling automático deshabilitado: faltan modelos Ollama: %s.",
                        ", ".join(sorted(missing_models)),
                    )
                else:
                    _gmail_poll_task = asyncio.create_task(_poll_gmail())
            except (httpx.HTTPError, ValueError):
                logger.warning(
                    "Polling automático deshabilitado: Ollama no responde en %s.",
                    settings.OLLAMA_BASE_URL,
                )

    try:
        yield
    finally:
        if _gmail_poll_task is not None:
            _gmail_poll_task.cancel()
            try:
                await _gmail_poll_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Agente Explorador de Gmail API",
    version="1.0.0",
    description="Backend SDD para ingesta, procesamiento y gestion documental",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend FastAPI operativo y conectado a PostgreSQL"}


@app.get("/api/v1/health/db", tags=["Health Check"])
async def test_db_connection(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "database": "plataforma_agente",
            "message": "Conexion con PostgreSQL y pgvector establecida correctamente!",
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"No se pudo conectar a la base de datos: {str(exc)}",
        }

@app.get("/health")
async def health_check():
    return {"status": "ok"}
