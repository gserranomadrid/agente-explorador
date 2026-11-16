import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.api.v1.endpoints.emails import (
    classify_pending_emails,
    submit_email_feedback,
    sync_emails,
)
from app.models.tables import Correo, Evento, MemoriaEpisodica
from app.services.cognition import (
    CategoriaCorreo,
    ClasificacionCorreo,
    RetroalimentacionCorreo,
)


class Result:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.value


class FakeDatabase:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.commits = 0
        self.flushes = 0

    async def execute(self, query):
        self.last_query = query
        return self.results.pop(0) if self.results else Result()

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1
        for item in self.added:
            if isinstance(item, Correo) and item.id is None:
                item.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


class FakeGmailService:
    def fetch_inbox_emails(self):
        return [
            {
                "message_id": "message-1",
                "thread_id": "thread-1",
                "sender": "sender@example.com",
                "subject": "Asunto",
                "received_at": datetime.now(timezone.utc),
                "body_text": "Cuerpo",
                "attachments": [],
            }
        ]


class FakeCognitionService:
    vector_service = SimpleNamespace(build_embedding_payload=lambda values: values)

    @staticmethod
    def build_input(subject, sender, body):
        result = f"{subject} {sender} {body}"
        return result

    async def classify_email(self, subject, sender, body, db):
        self.last_input = self.build_input(subject, sender, body)
        self.last_db = db
        return sample_classification(), [0.1] * 768


class OfflineCognitionService(FakeCognitionService):
    async def classify_email(self, subject, sender, body, db):
        del subject, sender, body, db
        raise httpx.ConnectError("Ollama no responde")


def sample_classification(category=CategoriaCorreo.FINANCIERO):
    return ClasificacionCorreo(
        razonamiento="Se refiere a una factura.",
        categoria=category,
        dependencia_emisora="Proveedor",
        tipo_documento="Factura",
        periodo="Noviembre 2026",
        nivel_confianza=0.9,
    )


class EmailAgentFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_saves_email_and_reports_local_model_unavailable(self):
        db = FakeDatabase(results=[Result(rows=[])])
        with (
            patch(
                "app.api.v1.endpoints.emails.GmailService",
                FakeGmailService,
            ),
            patch(
                "app.api.v1.endpoints.emails.CognitionService",
                OfflineCognitionService,
            ),
        ):
            response = await sync_emails(db)

        saved_email = next(item for item in db.added if isinstance(item, Correo))
        audit_event = next(
            item
            for item in db.added
            if isinstance(item, Evento)
            and item.tipo_evento == "sincronizacion_gmail_completada"
        )
        self.assertEqual(saved_email.estado_procesamiento, "ERROR_CLASIFICACION")
        self.assertEqual(response["errores_clasificacion"], 1)
        self.assertEqual(response["clasificaciones_realizadas"], 0)
        self.assertIn("Ollama no responde", response["detalle_errores_clasificacion"][0])
        self.assertEqual(audit_event.tipo_evento, "sincronizacion_gmail_completada")
        self.assertEqual(db.commits, 1)

    async def test_sync_links_agent_memory_to_new_email(self):
        db = FakeDatabase(results=[Result(rows=[])])
        with (
            patch(
                "app.api.v1.endpoints.emails.GmailService",
                FakeGmailService,
            ),
            patch(
                "app.api.v1.endpoints.emails.CognitionService",
                FakeCognitionService,
            ),
        ):
            response = await sync_emails(db)

        saved_email = next(item for item in db.added if isinstance(item, Correo))
        memory = next(item for item in db.added if isinstance(item, MemoriaEpisodica))
        self.assertEqual(response["clasificaciones_realizadas"], 1)
        self.assertEqual(memory.correo_id, saved_email.id)
        self.assertEqual(saved_email.clasificacion["categoria"], "Financiero")

    async def test_pending_emails_can_be_classified_without_gmail_sync(self):
        email = Correo(
            id=uuid.uuid4(),
            message_id="pending-message",
            thread_id="thread-1",
            remitente="proveedor@example.com",
            asunto="Factura",
            fecha_recepcion=datetime.now(timezone.utc),
            cuerpo_texto="Factura del mes",
            estado_procesamiento="PENDIENTE",
        )
        db = FakeDatabase(results=[Result(rows=[email])])
        with patch(
            "app.api.v1.endpoints.emails.CognitionService",
            FakeCognitionService,
        ):
            response = await classify_pending_emails(limit=10, db=db)

        self.assertEqual(response["pendientes_encontrados"], 1)
        self.assertEqual(response["clasificaciones_realizadas"], 1)
        self.assertEqual(email.clasificacion["categoria"], "Financiero")
        self.assertEqual(email.estado_procesamiento, "PROCESADO")
        self.assertTrue(any(isinstance(item, MemoriaEpisodica) for item in db.added))
        self.assertEqual(db.commits, 1)

    async def test_feedback_updates_email_and_episode_memory(self):
        original = sample_classification(CategoriaCorreo.INDEFINIDO).model_dump(
            mode="json"
        )
        correo = Correo(
            id=uuid.uuid4(),
            message_id="message-1",
            thread_id="thread-1",
            remitente="sender@example.com",
            asunto="Asunto",
            fecha_recepcion=datetime.now(timezone.utc),
            clasificacion=original,
        )
        memory = MemoriaEpisodica(
            correo_id=correo.id,
            decision_agente={**original, "entrada": "correo"},
            fue_correcto=False,
        )
        db = FakeDatabase(
            results=[
                Result(value=correo),
                Result(value=memory),
                Result(rows=[]),
            ]
        )
        feedback = RetroalimentacionCorreo(clasificacion=sample_classification())

        response = await submit_email_feedback(correo.id, feedback, db)

        self.assertEqual(response["status"], "success")
        self.assertEqual(correo.clasificacion["categoria"], "Financiero")
        self.assertEqual(correo.estado_procesamiento, "CORREGIDO")
        self.assertEqual(memory.correccion_usuario["categoria"], "Financiero")
        self.assertFalse(memory.fue_correcto)
        self.assertEqual(db.commits, 1)
        self.assertTrue(any(isinstance(item, Evento) for item in db.added))


if __name__ == "__main__":
    unittest.main()
