import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.database.models import Invoice, Vendor, ValidationLog
from config.settings import settings
from src.ingestion.email_client import get_email_ingestor
from src.ingestion.parser import InvoiceFileParser
from src.reporting.excel_service import ExcelReportingService
from src.validation.service import InvoiceProcessingService
from src.validation.validator import InvoiceSQLValidator
from src.extraction.schemas import ExtractedInvoiceData
from src.api.schemas import (
    InvoiceSummaryResponse,
    InvoiceDetailResponse,
    SyncEmailsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invoices", tags=["Invoices & Accounting"])


def _map_invoice_summary(inv: Invoice) -> InvoiceSummaryResponse:
    """Mapea una entidad Invoice a InvoiceSummaryResponse asegurando datos de proveedor y PO."""
    return InvoiceSummaryResponse(
        id=inv.id,
        invoice_number=inv.invoice_number,
        uuid=inv.uuid,
        vendor_id=inv.vendor_id,
        vendor_name=inv.vendor.name if inv.vendor else None,
        vendor_tax_id=inv.vendor.tax_id if inv.vendor else None,
        po_number=inv.purchase_order.po_number if inv.purchase_order else None,
        issue_date=inv.issue_date,
        currency=inv.currency,
        subtotal=inv.subtotal,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        status=inv.status,
        source_file=inv.source_file,
        created_at=inv.created_at,
    )


@router.post("/sync-emails", response_model=SyncEmailsResponse)
def sync_emails(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Lee correos no procesados del buzón (IMAP o Mock), extrae facturas con LLM y valida vía SQL."""
    ingestor = get_email_ingestor()
    emails = ingestor.fetch_unprocessed_emails(limit=limit)

    service = InvoiceProcessingService(db)
    processed_invoices: List[InvoiceSummaryResponse] = []
    errors: List[str] = []

    for email_msg in emails:
        for att in email_msg.attachments:
            try:
                text_content = att.extracted_text or InvoiceFileParser.extract_text(att.filename, att.content_bytes)
                if not text_content.strip():
                    errors.append(f"Adjunto '{att.filename}' en correo '{email_msg.subject}' no contiene texto extraíble.")
                    continue

                inv = service.process_invoice_text(text_content, source_file=att.filename)
                processed_invoices.append(_map_invoice_summary(inv))

            except Exception as e:
                db.rollback()
                logger.error(f"Error procesando {att.filename}: {e}")
                errors.append(f"Error en '{att.filename}': {str(e)}")

    return SyncEmailsResponse(
        processed_count=len(processed_invoices),
        invoices=processed_invoices,
        errors=errors,
    )


@router.post("/upload", response_model=InvoiceDetailResponse)
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Sube directamente una factura (PDF, TXT, XML) para su extracción con LLM y validación contable."""
    content_bytes = await file.read()
    text_content = InvoiceFileParser.extract_text(file.filename, content_bytes)

    if not text_content.strip():
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo extraer contenido textual del archivo '{file.filename}'. Verifique el formato.",
        )

    service = InvoiceProcessingService(db)
    try:
        inv = service.process_invoice_text(text_content, source_file=file.filename)
        return inv
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante el procesamiento: {str(e)}")


@router.get("", response_model=List[InvoiceSummaryResponse])
def list_invoices(
    status: Optional[str] = Query(None, description="Filtrar por estado: VALIDATED, PENDING_REVIEW, REJECTED"),
    vendor_tax_id: Optional[str] = Query(None, description="Filtrar por RFC del proveedor"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Obtiene el listado de facturas procesadas con filtros por estado o proveedor."""
    query = db.query(Invoice)

    if status:
        query = query.filter(Invoice.status == status.upper())

    if vendor_tax_id:
        query = query.join(Vendor).filter(Vendor.tax_id == vendor_tax_id.upper())

    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    return [_map_invoice_summary(inv) for inv in invoices]


@router.get("/export/excel")
def export_invoices_excel(
    status: Optional[str] = Query(None, description="Filtrar por estado para el reporte"),
    db: Session = Depends(get_db),
):
    """Exporta el consolidado de facturas validadas a un archivo Excel (.xlsx) corporativo."""
    query = db.query(Invoice)
    if status:
        query = query.filter(Invoice.status == status.upper())

    invoices = query.order_by(Invoice.id.asc()).all()
    excel_bytes = ExcelReportingService.generate_invoices_report(invoices)

    filename = f"reporte_facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/stats")
def get_invoice_stats(db: Session = Depends(get_db)):
    """Retorna métricas consolidadas para el dashboard ejecutivo."""
    invoices = db.query(Invoice).all()
    total = len(invoices)
    validated = sum(1 for inv in invoices if inv.status == "VALIDATED")
    rejected = sum(1 for inv in invoices if inv.status == "REJECTED")
    pending = sum(1 for inv in invoices if inv.status == "PENDING_REVIEW")
    total_amount = sum(inv.total_amount for inv in invoices if inv.status == "VALIDATED")
    approval_rate = round((validated / total * 100), 1) if total > 0 else 0.0

    return {
        "total_invoices": total,
        "validated_count": validated,
        "rejected_count": rejected,
        "pending_count": pending,
        "total_amount_validated": total_amount,
        "approval_rate": approval_rate,
    }


@router.get("/samples")
def list_sample_invoices():
    """Retorna la lista de facturas de muestra disponibles para pruebas de demostración."""
    samples_dir = settings.SAMPLES_DIR
    if not samples_dir.exists():
        return []
    result = []
    descriptions = {
        "factura_valida_tech.txt": {"title": "Factura Válida (Tecnología)", "type": "valid", "desc": "Proveedor activo, orden de compra coincidente y aritmética correcta."},
        "factura_valida_papeleria.txt": {"title": "Factura Válida (Papelería)", "type": "valid", "desc": "Suministros de oficina con clasificación RAG a gastos operativos."},
        "factura_error_aritmetico.txt": {"title": "Error Aritmético", "type": "invalid", "desc": "Discrepancia forzada en suma de subtotal + IVA contra el total."},
        "factura_proveedor_invalido.txt": {"title": "Proveedor No Registrado", "type": "invalid", "desc": "RFC desconocido en el catálogo de proveedores activos."},
    }
    for file in sorted(samples_dir.glob("*.txt")):
        meta = descriptions.get(file.name, {"title": file.name, "type": "neutral", "desc": "Muestra de prueba"})
        result.append({
            "filename": file.name,
            "title": meta["title"],
            "type": meta["type"],
            "description": meta["desc"],
        })
    return result


@router.post("/samples/{filename}/process", response_model=InvoiceDetailResponse)
def process_sample_invoice(filename: str, db: Session = Depends(get_db)):
    """Procesa una factura de muestra preconfigurada directamente sin necesidad de subir archivo."""
    sample_path = settings.SAMPLES_DIR / filename
    if not sample_path.exists() or not sample_path.is_file():
        raise HTTPException(status_code=404, detail=f"Muestra '{filename}' no encontrada.")

    text_content = sample_path.read_text(encoding="utf-8")
    service = InvoiceProcessingService(db)
    try:
        inv = service.process_invoice_text(text_content, source_file=filename)
        return inv
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando muestra: {str(e)}")


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de una factura con sus partidas y logs de auditoría SQL."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Factura #{invoice_id} no encontrada.")
    return inv


@router.post("/{invoice_id}/revalidate", response_model=InvoiceDetailResponse)
def revalidate_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Re-ejecuta el motor de reglas SQL sobre una factura previamente registrada."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Factura #{invoice_id} no encontrada.")

    if not inv.extracted_raw_json:
        raise HTTPException(status_code=400, detail="La factura no cuenta con datos crudos JSON para revalidar.")

    extracted = ExtractedInvoiceData.model_validate_json(inv.extracted_raw_json)
    validator = InvoiceSQLValidator(db)
    report = validator.validate(extracted, existing_invoice_id=inv.id)

    # Actualizar estado e IDs
    inv.status = report.overall_status
    inv.vendor_id = report.vendor_id
    inv.po_id = report.po_id

    # Limpiar y regenerar logs
    inv.validation_logs.clear()
    for res in report.results:
        inv.validation_logs.append(
            ValidationLog(
                invoice_id=inv.id,
                rule_name=res.rule_name,
                passed=res.passed,
                severity=res.severity,
                message=res.message,
            )
        )

    db.commit()
    db.refresh(inv)
    return inv
