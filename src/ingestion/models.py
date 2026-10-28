from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class EmailAttachment:
    """Representa un archivo adjunto extraído de un correo."""
    filename: str
    content_type: str
    content_bytes: bytes
    extracted_text: Optional[str] = None


@dataclass
class EmailMessagePayload:
    """Estructura estandarizada de un correo electrónico recibido."""
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    attachments: List[EmailAttachment] = field(default_factory=list)

