import io
import logging
from typing import Optional
import pypdf

logger = logging.getLogger(__name__)


class InvoiceFileParser:
    """Extrae el contenido textual de archivos adjuntos (PDFs, TXT, etc.)."""

    @staticmethod
    def extract_text(filename: str, content_bytes: bytes) -> str:
        """Extrae texto según la extensión del archivo."""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

        if ext == "pdf":
            return InvoiceFileParser._extract_from_pdf(content_bytes)
        elif ext in ("txt", "csv", "xml", "json"):
            return content_bytes.decode("utf-8", errors="replace")
        else:
            # Fallback para archivos de texto plano o no estructurados
            try:
                return content_bytes.decode("utf-8")
            except Exception:
                return ""

    @staticmethod
    def _extract_from_pdf(content_bytes: bytes) -> str:
        """Extrae texto de todas las páginas de un archivo PDF usando pypdf."""
        try:
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n--- Page Break ---\n".join(pages_text)
        except Exception as e:
            logger.error(f"Error al extraer texto del PDF: {e}")
            return ""
