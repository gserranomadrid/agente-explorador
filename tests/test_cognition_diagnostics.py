import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.v1.endpoints.cognition import (
    ExtractionRuleCreate,
    SemanticSearchRequest,
    create_extraction_rule,
    get_cognition_diagnostics,
    search_similar_memories,
)


class Result:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def one(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows


class CognitionDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_rule_creation_saves_normalized_active_rule(self):
        class FakeDatabase:
            def __init__(self):
                self.added = []

            def add(self, item):
                self.added.append(item)

            async def commit(self):
                pass

            async def refresh(self, item):
                pass

        database = FakeDatabase()
        request = ExtractionRuleCreate(
            category="Financiero",
            subject_pattern="  factura ",
            sender_pattern=" ",
            instruction="  Validar que se mencione un pago.  ",
        )

        response = await create_extraction_rule(request, database)

        self.assertEqual(response["category"], "Financiero")
        self.assertEqual(response["subject_pattern"], "factura")
        self.assertIsNone(response["sender_pattern"])
        self.assertEqual(response["instruction"], "Validar que se mencione un pago.")
        self.assertTrue(response["is_active"])
        self.assertEqual(len(database.added), 1)

    async def test_diagnostics_show_memory_summary_without_email_input(self):
        memory = SimpleNamespace(
            id="memory-1",
            created_at="2026-11-15T00:00:00Z",
            decision_agente={
                "entrada": "correo privado",
                "categoria": "Financiero",
                "nivel_confianza": 0.8,
            },
            correccion_usuario={
                "categoria": "Administrativo",
                "dependencia_emisora": "Personal",
            },
            fue_correcto=False,
        )
        rule = SimpleNamespace(
            categoria="Financiero",
            patron_asunto="factura",
            patron_remitente=None,
            prompt_instruccion="Priorizar facturas.",
        )
        database = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    Result(value=(1, 1)),
                    Result(rows=[memory]),
                    Result(rows=[rule]),
                ]
            )
        )

        with patch(
            "app.api.v1.endpoints.cognition._ollama_status",
            AsyncMock(return_value={"connected": True}),
        ):
            result = await get_cognition_diagnostics(database)

        self.assertEqual(result["memory"]["total"], 1)
        self.assertEqual(result["memory"]["with_feedback"], 1)
        self.assertEqual(result["memory"]["recent"][0]["review_status"], "corregida")
        self.assertEqual(
            result["memory"]["recent"][0]["decision"]["categoria"],
            "Financiero",
        )
        self.assertNotIn(
            "entrada",
            result["memory"]["recent"][0]["decision"],
        )
        self.assertEqual(result["active_rules"][0]["instruction"], "Priorizar facturas.")

    async def test_semantic_search_returns_only_safe_match_fields(self):
        class FakeCognition:
            async def embed_text(self, text):
                self.query = text
                return [0.1, 0.2]

            async def find_similar_feedback(self, db, embedding):
                return [
                    {
                        "input": "correo privado",
                        "label": {
                            "categoria": "Financiero",
                            "dependencia_emisora": "Proveedor",
                        },
                        "similarity": 0.9,
                        "memory_id": "memory-1",
                        "created_at": "2026-11-15T00:00:00Z",
                        "was_correct": False,
                    }
                ]

        with patch(
            "app.api.v1.endpoints.cognition.CognitionService",
            FakeCognition,
        ):
            result = await search_similar_memories(
                SemanticSearchRequest(query="factura"),
                db=None,
            )

        self.assertEqual(result["results"][0]["similarity"], 0.9)
        self.assertEqual(
            result["results"][0]["classification"]["categoria"],
            "Financiero",
        )
        self.assertNotIn("input", result["results"][0])
        self.assertNotIn("label", result["results"][0])


if __name__ == "__main__":
    unittest.main()
