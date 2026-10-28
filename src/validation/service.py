from datetime import datetime, timezone
import json
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from src.database.models import Invoice, InvoiceItem, ValidationLog
from src.extraction.extractor import get_invoice_extractor
from src.extraction.schemas import ExtractedInvoiceData
from src.rag.catalog_matcher import SemanticCatalogMatcher
from src.validation.validator import InvoiceSQLValidator
from src.validation.rules import ValidationReport

logger = logging.getLogger(__name__)


class InvoiceProcessingService:
    """Servicio orquestador del flujo integral de procesamiento contable."""

    def __init__(self, db: Session):
        self.db = db
        self.extractor = get_invoice_extractor()
        self.validator = InvoiceSQLValidator(db)
        self.catalog_matcher = SemanticCatalogMatcher(db)

    def process_invoice_text(
        self,
        document_text: str,
        source_file: Optional[str] = None
    ) -> Invoice:
        """Flujo completo: Extracción LLM -> RAG de Catálogo -> Validación SQL -> Persistencia."""

        # 1. Extracción con LLM
        extracted: ExtractedInvoiceData = self.extractor.extract_from_text(document_text)

        # 2. Validación contable contra BD vía SQL
        report: ValidationReport = self.validator.validate(extracted)

        # 3. Parsear fecha de emisión
        parsed_date = None
        if extracted.issue_date:
            try:
                parsed_date = datetime.strptime(extracted.issue_date, "%Y-%m-%d").date()
            except Exception:
                pass

        # 4. Crear registro en BD
        invoice = Invoice(
            invoice_number=extracted.invoice_number,
            uuid=extracted.uuid,
            vendor_id=report.vendor_id,
            po_id=report.po_id,
            issue_date=parsed_date,
            currency=extracted.currency,
            subtotal=extracted.subtotal,
            tax_amount=extracted.tax_amount,
            total_amount=extracted.total_amount,
            status=report.overall_status,
            source_file=source_file,
            extracted_raw_json=extracted.model_dump_json(),
        )
        self.db.add(invoice)
        self.db.flush()  # Obtener invoice.id

        # 5. Partidas y Clasificación Semántica (RAG)
        for item in extracted.items:
            # Mapear descripción libre con cuenta contable usando similitud semántica
            matched_code, score = self.catalog_matcher.match_item(item.description)

            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price,
                accounting_account_code=matched_code,
            )
            self.db.add(inv_item)

        # 6. Guardar Logs de Auditoría SQL
        for res in report.results:
            log_entry = ValidationLog(
                invoice_id=invoice.id,
                rule_name=res.rule_name,
                passed=res.passed,
                severity=res.severity,
                message=res.message,
            )
            self.db.add(log_entry)

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

