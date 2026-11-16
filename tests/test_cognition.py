import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from app.services.cognition import (
    CategoriaCorreo,
    ClasificacionCorreo,
    CognitionService,
)


def classification(category, confidence):
    return ClasificacionCorreo(
        razonamiento="Factura indicada en el correo.",
        categoria=category,
        dependencia_emisora="Proveedor",
        tipo_documento="Factura",
        periodo="Noviembre 2026",
        nivel_confianza=confidence,
    )


class CognitionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_ambiguous_email_retries_with_similar_corrected_examples(self):
        uncertain = classification(CategoriaCorreo.INDEFINIDO, 0.4)
        resolved = classification(CategoriaCorreo.FINANCIERO, 0.9)
        service = CognitionService()
        service.embed_text = AsyncMock(return_value=[0.1] * 768)
        service._matching_rules = AsyncMock(return_value=[])
        service._classify = AsyncMock(side_effect=[uncertain, resolved])
        service._find_similar_feedback = AsyncMock(
            return_value=[
                {
                    "input": "ASUNTO: Pago\nCUERPO: Factura",
                    "output": '{"categoria":"Financiero"}',
                }
            ]
        )

        result, embedding = await service.classify_email(
            "Solicitud", "proveedor@example.com", "Información adjunta", None
        )

        self.assertEqual(result.categoria, CategoriaCorreo.FINANCIERO)
        self.assertEqual(len(embedding), 768)
        self.assertEqual(service._classify.await_count, 2)
        self.assertEqual(
            service._classify.await_args_list[1].kwargs["examples"][0]["input"],
            "ASUNTO: Pago\nCUERPO: Factura",
        )

    async def test_ollama_chat_uses_json_schema_and_parses_classification(self):
        expected = classification(CategoriaCorreo.FINANCIERO, 0.93)

        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "qwen2.5:3b")
            self.assertEqual(payload["stream"], False)
            self.assertIn("categoria", payload["format"]["properties"])
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": expected.model_dump_json()
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = CognitionService(http_client=client)
            result = await service._classify("ASUNTO: Pago")

        self.assertEqual(result, expected)

    async def test_percentage_confidence_is_normalized_to_zero_to_one(self):
        expected = classification(CategoriaCorreo.FINANCIERO, 0.85)

        def handler(request):
            payload = expected.model_dump(mode="json")
            payload["nivel_confianza"] = 85
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps(payload)}},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = CognitionService(http_client=client)
            result = await service._classify("ASUNTO: Pago")

        self.assertEqual(result.nivel_confianza, 0.85)

    async def test_confidence_over_percentage_range_is_rejected(self):
        expected = classification(CategoriaCorreo.FINANCIERO, 0.85)

        def handler(request):
            payload = expected.model_dump(mode="json")
            payload["nivel_confianza"] = 101
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps(payload)}},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = CognitionService(http_client=client)
            with self.assertRaisesRegex(ValueError, "cumpla el esquema"):
                await service._classify("ASUNTO: Pago")

    async def test_ollama_embeddings_allow_local_model_dimensions(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "nomic-embed-text")
            return httpx.Response(
                200,
                json={"embeddings": [[0.25, 0.5, 0.75]]},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = CognitionService(http_client=client)
            result = await service.embed_text("texto de prueba")

        self.assertEqual(result, [0.25, 0.5, 0.75])

    async def test_invalid_embedding_values_are_rejected(self):
        service = CognitionService()
        service._post = AsyncMock(
            return_value={"embeddings": [[float("nan"), 0.1]]}
        )

        with self.assertRaisesRegex(ValueError, "finitos"):
            await service.embed_text("texto")

    async def test_semantic_search_returns_only_relevant_corrected_memories(self):
        corrected = {
            "razonamiento": "Factura según el texto.",
            "categoria": "Financiero",
            "dependencia_emisora": "Proveedor",
            "tipo_documento": "Factura",
            "periodo": "Noviembre 2026",
            "nivel_confianza": 0.9,
        }
        memory = SimpleNamespace(
            id=uuid.uuid4(),
            decision_agente={"entrada": "ASUNTO: Pago"},
            correccion_usuario=corrected,
            created_at=None,
            fue_correcto=False,
        )
        database = SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    all=lambda: [(memory, 0.1), (memory, 0.5)]
                )
            )
        )

        matches = await CognitionService().find_similar_feedback(
            database,
            [0.1, 0.2],
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["label"], corrected)
        self.assertAlmostEqual(matches[0]["similarity"], 0.9)
        self.assertFalse(matches[0]["was_correct"])


if __name__ == "__main__":
    unittest.main()
