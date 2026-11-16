from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tables import Documento
from app.schemas.domain import DocumentoSchema
from app.services.storage_service import StorageService

router = APIRouter()
storage_service = StorageService()


@router.post("/upload", response_model=DocumentoSchema, status_code=201)
async def upload_document(
    correo_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Sube un documento validando deduplicaci?n por Hashing SHA-256."""
    content = await file.read()
    file_hash = storage_service.calculate_sha256(content)

    stmt = select(Documento).where(Documento.hash_sha256 == file_hash)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"El archivo ya existe en la base de datos (SHA-256: {file_hash}).",
        )

    saved_path = storage_service.save_file(file.filename, content)

    nuevo_doc = Documento(
        id=uuid.uuid4(),
        correo_id=correo_id,
        nombre_archivo=storage_service.sanitize_filename(file.filename),
        tipo_mime=file.content_type or "application/octet-stream",
        tamanio_bytes=len(content),
        hash_sha256=file_hash,
        ruta_almacenamiento=saved_path,
        version=1,
    )
    db.add(nuevo_doc)
    await db.commit()
    await db.refresh(nuevo_doc)
    return nuevo_doc


@router.get("/", response_model=list[DocumentoSchema])
async def list_documents(db: AsyncSession = Depends(get_db)):
    """Lista todos los documentos almacenados."""
    result = await db.execute(select(Documento))
    return result.scalars().all()
