from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsuarioSchema(BaseModel):
    id: UUID
    email: str
    nombre: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorreoSchema(BaseModel):
    id: UUID
    message_id: str
    thread_id: str
    remitente: str
    asunto: Optional[str] = None
    fecha_recepcion: datetime
    cuerpo_texto: Optional[str] = None
    clasificacion: Optional[Dict[str, Any]] = None
    estado_procesamiento: str = "PENDIENTE"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentoSchema(BaseModel):
    id: UUID
    correo_id: UUID
    nombre_archivo: str
    tipo_mime: str
    tamanio_bytes: int
    hash_sha256: str
    ruta_almacenamiento: str
    version: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IndicadorSchema(BaseModel):
    id: UUID
    documento_id: UUID
    categoria: str
    dependencia: str
    metadatos_extraidos: Dict[str, Any]
    confianza_clasificacion: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
