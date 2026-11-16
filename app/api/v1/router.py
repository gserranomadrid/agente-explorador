from fastapi import APIRouter

from app.api.v1.endpoints import auth, cognition, documents, emails, events

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Autenticaci?n"])
router.include_router(emails.router, prefix="/emails", tags=["Correos"])
router.include_router(documents.router, prefix="/documents", tags=["Documentos"])
router.include_router(events.router, prefix="/events", tags=["Eventos"])
router.include_router(cognition.router, prefix="/cognition", tags=["Cognición"])

@router.get("/status")
async def api_status():
  return {"status": "online", "authenticated": True}