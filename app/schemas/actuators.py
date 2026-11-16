from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    categoria: str = Field(..., description="FINANCIERO, ACADEMICO, OPERATIVO, ADMINISTRATIVO")
    dependencia: str
    confianza: float = Field(..., ge=0.0, le=1.0)
    metadatos: Dict[str, Any]


class GuardarDocumentoDTO(BaseModel):
    correo_id: UUID
    nombre_archivo: str
    tipo_mime: str
    tamanio_bytes: int
    hash_sha256: str
    ruta_almacenamiento: str


class RegistrarEventoDTO(BaseModel):
    tipo_evento: str
    origen: str
    detalles: Dict[str, Any]
