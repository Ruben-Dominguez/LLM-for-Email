import abc
import email
from email import policy
import imaplib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from config.settings import settings
from src.ingestion.models import EmailMessagePayload, EmailAttachment
from src.ingestion.parser import InvoiceFileParser

logger = logging.getLogger(__name__)


class BaseEmailIngestor(abc.ABC):
    """Clase base abstracta para ingesta de correos electrónicos."""

    @abc.abstractmethod
    def fetch_unprocessed_emails(self, limit: int = 10) -> List[EmailMessagePayload]:
        """Obtiene la lista de correos no procesados con sus adjuntos."""
        pass


class IMAPEmailIngestor(BaseEmailIngestor):
    """Ingesta de correos en vivo conectándose a servidores IMAP vía SSL (Gmail, Outlook, etc.)."""

    def __init__(
        self,
        server: str = settings.IMAP_SERVER,
        port: int = settings.IMAP_PORT,
        user: str = settings.IMAP_USER,
        password: str = settings.IMAP_PASSWORD,
        folder: str = settings.IMAP_FOLDER,
    ):
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.folder = folder

    def fetch_unprocessed_emails(self, limit: int = 10) -> List[EmailMessagePayload]:
        emails_payload: List[EmailMessagePayload] = []

        if not self.user or not self.password:
            logger.warning("Credenciales IMAP no configuradas. Retornando lista vacía.")
            return emails_payload

        try:
            # Conexión SSL al servidor IMAP
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.user, self.password)
            mail.select(self.folder)

            # Buscar correos no leídos
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                return emails_payload

            mail_ids = messages[0].split()
            # Tomar los más recientes hasta el límite indicado
            mail_ids = mail_ids[-limit:] if len(mail_ids) > limit else mail_ids

            for mail_id in mail_ids:
                status, data = mail.fetch(mail_id, "(RFC822)")
                if status != "OK" or not data:
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email, policy=policy.default)

                attachments: List[EmailAttachment] = []
                body_text = ""

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        filename = part.get_filename()

                        if filename:
                            # Es un adjunto (ej. factura PDF)
                            payload = part.get_payload(decode=True)
                            if payload:
                                extracted_text = InvoiceFileParser.extract_text(filename, payload)
                                attachments.append(
                                    EmailAttachment(
                                        filename=filename,
                                        content_type=content_type,
                                        content_bytes=payload,
                                        extracted_text=extracted_text,
                                    )
                                )
                        elif content_type == "text/plain":
                            body_text += part.get_payload(decode=True).decode("utf-8", errors="replace")
                else:
                    body_text = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                # Parsear fecha
                date_str = msg.get("Date")
                received_date = datetime.now(timezone.utc)
                if date_str:
                    try:
                        received_date = email.utils.parsedate_to_datetime(date_str)
                    except Exception:
                        pass

                payload_obj = EmailMessagePayload(
                    message_id=str(msg.get("Message-ID", mail_id.decode())),
                    sender=str(msg.get("From", "Desconocido")),
                    subject=str(msg.get("Subject", "Sin Asunto")),
                    received_at=received_date,
                    body_text=body_text,
                    attachments=attachments,
                )
                emails_payload.append(payload_obj)

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Error durante la sincronización IMAP: {e}")

        return emails_payload


class MockEmailIngestor(BaseEmailIngestor):
    """Simulador de buzón de correos para pruebas locales y CI/CD sin credenciales externas."""

    def __init__(self, mock_dir: Path = settings.MOCK_INBOX_DIR):
        self.mock_dir = mock_dir

    def fetch_unprocessed_emails(self, limit: int = 10) -> List[EmailMessagePayload]:
        emails_payload: List[EmailMessagePayload] = []

        if not self.mock_dir.exists():
            return emails_payload

        # Leer archivos mock (.eml, .txt, .pdf)
        for filepath in list(self.mock_dir.glob("*"))[:limit]:
            if filepath.is_dir():
                continue

            with open(filepath, "rb") as f:
                content = f.read()

            extracted_text = InvoiceFileParser.extract_text(filepath.name, content)
            attachment = EmailAttachment(
                filename=filepath.name,
                content_type="application/pdf" if filepath.suffix == ".pdf" else "text/plain",
                content_bytes=content,
                extracted_text=extracted_text,
            )

            payload_obj = EmailMessagePayload(
                message_id=f"MOCK-MSG-{filepath.stem}",
                sender="facturacion@proveedor-demo.com",
                subject=f"Envío de factura {filepath.stem}",
                received_at=datetime.now(timezone.utc),
                body_text=f"Adjunto enviamos la factura correspondiente al archivo {filepath.name}.",
                attachments=[attachment],
            )
            emails_payload.append(payload_obj)

        return emails_payload


def get_email_ingestor() -> BaseEmailIngestor:
    """Fábrica de ingestores de correo según la configuración del entorno."""
    if settings.EMAIL_SOURCE == "imap":
        return IMAPEmailIngestor()
    return MockEmailIngestor()
