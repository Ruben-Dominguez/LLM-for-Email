import abc
import json
import logging
import re
from typing import Optional

from config.settings import settings
from src.extraction.schemas import ExtractedInvoiceData, ExtractedInvoiceItem
from src.extraction.prompts import (
    SYSTEM_INVOICE_EXTRACTION_PROMPT,
    FEW_SHOT_EXAMPLE,
    build_user_prompt,
)

logger = logging.getLogger(__name__)


class BaseInvoiceExtractor(abc.ABC):
    """Interfaz abstracta (Strategy) para extractores de facturas basados en LLM."""

    @abc.abstractmethod
    def extract_from_text(self, document_text: str) -> ExtractedInvoiceData:
        """Procesa el texto de la factura y retorna los datos estructurados en Pydantic."""
        pass

    def _clean_json_response(self, raw_response: str) -> str:
        """Limpia posibles bloques markdown (```json ... ```) si el modelo los incluye."""
        text = raw_response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text


class GeminiInvoiceExtractor(BaseInvoiceExtractor):
    """Extractor que utiliza la API de Google Gemini (google-genai)."""

    def __init__(self, api_key: Optional[str] = settings.GEMINI_API_KEY, model_name: str = settings.LLM_MODEL_NAME):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None

        if not self.api_key:
            logger.warning("GEMINI_API_KEY no configurada. Las llamadas a Gemini fallarán si no se provee.")

    @property
    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def extract_from_text(self, document_text: str) -> ExtractedInvoiceData:
        try:
            full_prompt = (
                f"{SYSTEM_INVOICE_EXTRACTION_PROMPT}\n\n"
                f"{FEW_SHOT_EXAMPLE}\n\n"
                f"{build_user_prompt(document_text)}"
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
            )

            cleaned_text = self._clean_json_response(response.text)
            parsed_dict = json.loads(cleaned_text)
            return ExtractedInvoiceData.model_validate(parsed_dict)

        except Exception as e:
            logger.error(f"Error en GeminiInvoiceExtractor: {e}")
            raise RuntimeError(f"Error procesando factura con Gemini: {e}") from e


class OpenAIInvoiceExtractor(BaseInvoiceExtractor):
    """Extractor compatible con OpenAI o proveedores compatibles (Groq, Together, Ollama)."""

    def __init__(self, api_key: Optional[str] = settings.OPENAI_API_KEY, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def extract_from_text(self, document_text: str) -> ExtractedInvoiceData:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_INVOICE_EXTRACTION_PROMPT + "\n" + FEW_SHOT_EXAMPLE},
                {"role": "user", "content": build_user_prompt(document_text)},
            ]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            raw_text = response.choices[0].message.content or "{}"
            parsed_dict = json.loads(self._clean_json_response(raw_text))
            return ExtractedInvoiceData.model_validate(parsed_dict)

        except Exception as e:
            logger.error(f"Error en OpenAIInvoiceExtractor: {e}")
            raise RuntimeError(f"Error procesando factura con OpenAI: {e}") from e


class MockInvoiceExtractor(BaseInvoiceExtractor):
    """Extractor determinista mediante expresiones regulares y patrones semánticos.

    Permite ejecutar la suite completa de pruebas, integración y demos locales
    sin requerir llamadas a APIs de pago o conexión a internet.
    """

    def extract_from_text(self, document_text: str) -> ExtractedInvoiceData:
        # 1. Extraer RFC / Tax ID
        rfc_match = re.search(r"RFC:\s*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})", document_text, re.IGNORECASE)
        vendor_tax_id = rfc_match.group(1).upper() if rfc_match else "DESCONOCIDO"

        # 2. Extraer Razón Social
        name_match = re.search(r"Raz[óo]n Social:\s*([^\n\r]+)", document_text, re.IGNORECASE)
        vendor_name = name_match.group(1).strip() if name_match else "Proveedor No Identificado"

        # 3. Extraer Folio / Número de Factura
        inv_match = re.search(r"(?:N[úu]mero de Factura|Factura\s*No|Folio|Invoice\s*(?:No|Number)):\s*([A-Z0-9\-_]+)", document_text, re.IGNORECASE)
        invoice_number = inv_match.group(1).strip() if inv_match else "FAC-UNKNOWN"

        # 4. Extraer UUID / Folio Fiscal
        uuid_match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", document_text)
        uuid_val = uuid_match.group(1).lower() if uuid_match else None

        # 5. Extraer Orden de Compra (PO)
        po_match = re.search(r"(?:Orden de Compra|PO|Purchase Order|O\.?C\.?):\s*([A-Z0-9\-_]+)", document_text, re.IGNORECASE)
        po_number = po_match.group(1).strip() if po_match else None

        # 6. Extraer Fecha
        date_match = re.search(r"(?:Fecha(?:\s+de\s+Emisi[óo]n)?):\s*(\d{4}-\d{2}-\d{2})", document_text, re.IGNORECASE)
        issue_date = date_match.group(1) if date_match else "2026-10-28"

        # 7. Extraer Moneda
        curr_match = re.search(r"Moneda:\s*([A-Z]{3})", document_text, re.IGNORECASE)
        currency = curr_match.group(1).upper() if curr_match else "MXN"

        # 8. Extraer Importes (Subtotal, IVA, Total)
        subtotal_match = re.search(r"SUBTOTAL:\s*\$?\s*([\d,]+\.?\d*)", document_text, re.IGNORECASE)
        subtotal = float(subtotal_match.group(1).replace(",", "")) if subtotal_match else 0.0

        tax_match = re.search(r"(?:IVA|IMPUESTOS.*?):\s*\$?\s*([\d,]+\.?\d*)", document_text, re.IGNORECASE)
        tax_amount = float(tax_match.group(1).replace(",", "")) if tax_match else 0.0

        # Evitar hacer match con 'SUBTOTAL:' asegurando límite de palabra previo que no sea 'SUB'
        total_match = re.search(r"(?<!SUB)\bTOTAL:\s*\$?\s*([\d,]+\.?\d*)", document_text, re.IGNORECASE)
        total_amount = float(total_match.group(1).replace(",", "")) if total_match else subtotal + tax_amount

        # 9. Extraer Conceptos / Partidas
        items = []
        concept_pattern = re.compile(
            r"(\d+(?:\.\d+)?)\s*\|\s*([^|]+?)\s*\|\s*\$?\s*([\d,]+\.?\d*)\s*\|\s*\$?\s*([\d,]+\.?\d*)",
            re.MULTILINE
        )
        for match in concept_pattern.finditer(document_text):
            qty = float(match.group(1))
            desc = match.group(2).strip()
            unit_p = float(match.group(3).replace(",", ""))
            tot_p = float(match.group(4).replace(",", ""))
            items.append(
                ExtractedInvoiceItem(
                    description=desc,
                    quantity=qty,
                    unit_price=unit_p,
                    total_price=tot_p,
                )
            )

        if not items:
            items.append(
                ExtractedInvoiceItem(
                    description="Servicios generales o conceptos no desglosados",
                    quantity=1.0,
                    unit_price=subtotal,
                    total_price=subtotal,
                )
            )

        return ExtractedInvoiceData(
            invoice_number=invoice_number,
            uuid=uuid_val,
            vendor_name=vendor_name,
            vendor_tax_id=vendor_tax_id,
            po_number=po_number,
            issue_date=issue_date,
            currency=currency,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            items=items,
            confidence_score=0.99,
            notes="Extracción procesada por motor determinista",
        )


def get_invoice_extractor() -> BaseInvoiceExtractor:
    """Fábrica para obtener la estrategia de extracción configurada."""
    provider = settings.LLM_PROVIDER
    if provider == "gemini":
        return GeminiInvoiceExtractor()
    elif provider == "openai":
        return OpenAIInvoiceExtractor()
    return MockInvoiceExtractor()
