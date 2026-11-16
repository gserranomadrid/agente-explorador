from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AdjuntoMetadata(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int
    attachment_id: str


class SensorPayload(BaseModel):
    message_id: str
    thread_id: str
    sender: str
    subject: str
    received_at: datetime
    body_plain: Optional[str] = None
    attachments_metadata: List[AdjuntoMetadata] = []
