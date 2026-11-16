from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tables import Correo, Documento, Evento, Indicador, MemoriaEpisodica
from app.schemas.domain import CorreoSchema
from app.services.cognition import CognitionService, RetroalimentacionCorreo
from app.services.event_service import EventService
from app.services.gmail_service import GmailService
from app.services.storage_service import StorageService

router = APIRouter()
storage_service = StorageService()


async def _classify_unclassified_emails(
    correos: list[Correo],
    db: AsyncSession,
    cognition: CognitionService,
    origin: str,
) -> tuple[int, list[str]]:
    classified_count = 0
    errors = []
    for correo in correos:
        if correo.clasificacion is not None:
            continue
        try:
            classification, embedding = await cognition.classify_email(
                correo.asunto,
                correo.remitente,
                correo.cuerpo_texto,
                db,
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            correo.estado_procesamiento = "ERROR_CLASIFICACION"
            errors.append(f"{correo.message_id}: {type(exc).__name__}: {exc}")
            db.add(
                Evento(
                    **EventService.build_event(
                        tipo_evento="clasificacion_correo_fallida",
                        origen=origin,
                        detalles={
                            "message_id": correo.message_id,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                    )
                )
            )
            continue

        classification_data = classification.model_dump(mode="json")
        correo.clasificacion = classification_data
        correo.estado_procesamiento = (
            "PENDIENTE_REVISION"
            if classification.nivel_confianza <= 0.65
            else "PROCESADO"
        )
        decision = {
            **classification_data,
            "entrada": cognition.build_input(
                correo.asunto,
                correo.remitente,
                correo.cuerpo_texto,
            ),
        }
        db.add(
            MemoriaEpisodica(
                correo_id=correo.id,
                decision_agente=decision,
                fue_correcto=False,
                embedding=embedding,
            )
        )
        db.add(
            Evento(
                **EventService.build_event(
                    tipo_evento="correo_clasificado",
                    origen=origin,
                    detalles={
                        "message_id": correo.message_id,
                        "categoria": classification.categoria.value,
                        "confianza": classification.nivel_confianza,
                        "estado": correo.estado_procesamiento,
                    },
                )
            )
        )
        classified_count += 1

    await db.flush()
    return classified_count, errors


@router.post("/sync")
async def sync_emails(db: AsyncSession = Depends(get_db)):
  try:
    service = GmailService()
    cognition = CognitionService()
    emails = service.fetch_inbox_emails()
    message_ids = [email["message_id"] for email in emails]
    existing = {}
    if message_ids:
      result = await db.execute(
          select(Correo).where(Correo.message_id.in_(message_ids))
      )
      existing = {correo.message_id: correo for correo in result.scalars().all()}

    nuevos = 0
    documentos_guardados = 0
    hashes_procesados = set()
    for email in emails:
      correo = existing.get(email["message_id"])
      if correo is None:
        correo = Correo(message_id=email["message_id"])
        db.add(correo)
        nuevos += 1

      correo.thread_id = email["thread_id"]
      correo.remitente = email["sender"]
      correo.asunto = email["subject"]
      correo.fecha_recepcion = email["received_at"]
      correo.cuerpo_texto = email["body_text"]
      existing[email["message_id"]] = correo

    await db.flush()

    clasificaciones_realizadas, errores_clasificacion = (
        await _classify_unclassified_emails(
            [existing[email["message_id"]] for email in emails],
            db,
            cognition,
            "emails.sync",
        )
    )

    for email in emails:
      correo = existing.get(email["message_id"])
      classification = correo.clasificacion
      for attachment in email.get("attachments", []):
        content = attachment["content"]
        file_hash = storage_service.calculate_sha256(content)
        if file_hash in hashes_procesados:
          continue
        hashes_procesados.add(file_hash)

        result = await db.execute(
            select(Documento).where(Documento.hash_sha256 == file_hash)
        )
        documento = result.scalar_one_or_none()
        if documento is None:
          saved_path = storage_service.save_file(attachment["filename"], content)
          documento = Documento(
                correo_id=correo.id,
                nombre_archivo=storage_service.sanitize_filename(attachment["filename"]),
                tipo_mime=attachment["mime_type"],
                tamanio_bytes=len(content),
                hash_sha256=file_hash,
                ruta_almacenamiento=saved_path,
            )
          db.add(documento)
          documentos_guardados += 1

        if classification and documento.vector_embedding is None:
          documento.vector_embedding = cognition.vector_service.build_embedding_payload(
              await cognition.embed_text(
                  f"{classification.get('categoria', '')} "
                  f"{correo.asunto or ''} {attachment['filename']} "
                  f"{correo.cuerpo_texto or ''}"
              )
          )

        if classification:
          indicador_result = await db.execute(
              select(Indicador.id)
              .where(Indicador.documento_id == documento.id)
              .limit(1)
          )
          if indicador_result.scalar_one_or_none() is None:
            db.add(
                Indicador(
                    documento_id=documento.id,
                    categoria=classification["categoria"],
                    dependencia=classification["dependencia_emisora"],
                    metadatos_extraidos={
                        "tipo_documento": classification["tipo_documento"],
                        "periodo": classification["periodo"],
                        "razonamiento": classification["razonamiento"],
                    },
                    confianza_clasificacion=classification["nivel_confianza"],
                )
            )

    db.add(
        Evento(
            **EventService.build_event(
                tipo_evento="sincronizacion_gmail_completada",
                origen="emails.sync",
                detalles={
                    "correos_sincronizados": len(emails),
                    "correos_nuevos": nuevos,
                    "documentos_guardados": documentos_guardados,
                    "clasificaciones_realizadas": clasificaciones_realizadas,
                    "errores_clasificacion": len(errores_clasificacion),
                    "estado": "exitoso",
                },
            )
        )
    )
    await db.commit()
    return {
        "status": "success",
        "count": len(emails),
        "correos_sincronizados": len(emails),
        "nuevos": nuevos,
        "documentos_guardados": documentos_guardados,
        "clasificaciones_realizadas": clasificaciones_realizadas,
        "errores_clasificacion": len(errores_clasificacion),
        "detalle_errores_clasificacion": errores_clasificacion[:10],
    }
  except Exception as e:
    await db.rollback()
    db.add(
        Evento(
            **EventService.build_event(
                tipo_evento="sincronizacion_gmail_fallida",
                origen="emails.sync",
                detalles={
                    "estado": "fallido",
                    "error": f"{type(e).__name__}: {e}",
                },
            )
        )
    )
    try:
      await db.commit()
    except Exception as audit_error:
      await db.rollback()
      raise HTTPException(
          status_code=500,
          detail=(
              f"Error sincronizando correos: {e}. "
              f"No se pudo registrar el evento de auditoría: {audit_error}"
          ),
      ) from e
    raise HTTPException(status_code=500, detail=f"Error sincronizando correos: {e}") from e


@router.post("/classify-pending")
async def classify_pending_emails(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Correo)
        .where(Correo.clasificacion.is_(None))
        .order_by(Correo.fecha_recepcion.asc())
        .limit(limit)
    )
    correos = result.scalars().all()
    cognition = CognitionService()
    classified_count, errors = await _classify_unclassified_emails(
        correos,
        db,
        cognition,
        "emails.classify_pending",
    )
    await db.commit()
    return {
        "status": "success",
        "pendientes_encontrados": len(correos),
        "clasificaciones_realizadas": classified_count,
        "errores_clasificacion": len(errors),
        "detalle_errores_clasificacion": errors[:10],
    }


@router.get("/", response_model=list[CorreoSchema])
async def list_emails(db: AsyncSession = Depends(get_db)):
    """Lista los correos registrados."""
    result = await db.execute(select(Correo))
    return result.scalars().all()


@router.post("/{correo_id}/feedback")
async def submit_email_feedback(
    correo_id: UUID,
    feedback: RetroalimentacionCorreo,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Correo).where(Correo.id == correo_id))
    correo = result.scalar_one_or_none()
    if correo is None:
        raise HTTPException(status_code=404, detail="No se encontró el correo.")

    memory_result = await db.execute(
        select(MemoriaEpisodica)
        .where(MemoriaEpisodica.correo_id == correo.id)
        .order_by(MemoriaEpisodica.created_at.desc())
        .limit(1)
    )
    memory = memory_result.scalar_one_or_none()
    correction = feedback.clasificacion.model_dump(mode="json")
    if memory is None:
        raise HTTPException(
            status_code=409,
            detail="El correo no tiene una decisión del agente para corregir.",
        )

    original = memory.decision_agente
    memory.correccion_usuario = correction
    memory.fue_correcto = all(
        original.get(field) == correction[field]
        for field in (
            "categoria",
            "dependencia_emisora",
            "tipo_documento",
            "periodo",
        )
    )
    memory.retroalimentacion_texto = feedback.comentario
    correo.clasificacion = correction
    correo.estado_procesamiento = "PROCESADO" if memory.fue_correcto else "CORREGIDO"

    documents_result = await db.execute(
        select(Documento.id).where(Documento.correo_id == correo.id)
    )
    document_ids = documents_result.scalars().all()
    if document_ids:
        indicators_result = await db.execute(
            select(Indicador).where(Indicador.documento_id.in_(document_ids))
        )
        for indicator in indicators_result.scalars().all():
            indicator.categoria = correction["categoria"]
            indicator.dependencia = correction["dependencia_emisora"]
            indicator.metadatos_extraidos = {
                "tipo_documento": correction["tipo_documento"],
                "periodo": correction["periodo"],
                "razonamiento": correction["razonamiento"],
            }
            indicator.confianza_clasificacion = correction["nivel_confianza"]

    db.add(
        Evento(
            **EventService.build_event(
                tipo_evento="retroalimentacion_clasificacion",
                origen="emails.feedback",
                detalles={
                    "message_id": correo.message_id,
                    "categoria": correction["categoria"],
                    "decision_original_correcta": memory.fue_correcto,
                },
            )
        )
    )
    await db.commit()
    return {
        "status": "success",
        "message": "Retroalimentación registrada.",
        "decision_original_correcta": memory.fue_correcto,
    }
