from typing import Any, Dict


class EventService:
    """Servicio auxiliar para registrar eventos del flujo del agente."""

    @staticmethod
    def build_event(tipo_evento: str, origen: str, detalles: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "tipo_evento": tipo_evento,
            "origen": origen,
            "detalles": detalles,
        }
