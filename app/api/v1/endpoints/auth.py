from fastapi import APIRouter, HTTPException

from app.services.gmail_service import GmailService

router = APIRouter()
gmail_service = GmailService()


@router.get("/login")
def login_google():
    """Inicia o refresca la autenticaci?n local con Google OAuth 2.0."""
    try:
        gmail_service.authenticate()
        profile = gmail_service.get_user_profile()
        return {"status": "authenticated", "email": profile.get("emailAddress")}
    except Exception as exc:  # pragma: no cover - integraci?n externa
        raise HTTPException(status_code=500, detail=f"Error al autenticar con Google: {str(exc)}") from exc


@router.get("/status")
def check_auth_status():
    """Verifica si el token actual está activo y vigente."""
    try:
        profile = gmail_service.get_user_profile()
        return {"authenticated": True, "email": profile.get("emailAddress")}
    except Exception as exc:
        return {"authenticated": False, "detail": str(exc)}