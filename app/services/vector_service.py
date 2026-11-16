"""Módulo preparado para embeddings y almacenamiento vectorial con pgvector."""

from __future__ import annotations

import math


class VectorService:
    """Valida vectores generados por el modelo de embeddings local."""

    def __init__(self, dimension: int | None = None):
        self.dimension = dimension

    def build_embedding_payload(self, values: list[float]) -> list[float]:
        if self.dimension is not None and len(values) != self.dimension:
            raise ValueError(f"Se esperaban {self.dimension} dimensiones, pero recibieron {len(values)}.")
        if any(not isinstance(value, (int, float)) for value in values):
            raise ValueError("El embedding solo puede contener valores numéricos.")
        vector = [float(value) for value in values]
        if not vector or any(not math.isfinite(value) for value in vector):
            raise ValueError("El embedding debe contener valores numéricos finitos.")
        return vector
