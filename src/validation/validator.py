import logging
from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import settings
from src.extraction.schemas import ExtractedInvoiceData
from src.validation.rules import RuleResult, ValidationReport

logger = logging.getLogger(__name__)


class InvoiceSQLValidator:
    """Motor de validación contable que ejecuta consultas SQL contra la base de datos."""

    def __init__(self, db: Session, po_tolerance: float = settings.PO_TOLERANCE_PERCENTAGE):
        self.db = db
        self.po_tolerance = po_tolerance

    def validate(self, invoice_data: ExtractedInvoiceData, existing_invoice_id: Optional[int] = None) -> ValidationReport:
        """Aplica todas las reglas de negocio contables mediante consultas SQL."""
        results: List[RuleResult] = []

        # 1. Validación SQL: Existencia y estado activo del Proveedor
        vendor_id, vendor_res = self._validate_vendor(invoice_data.vendor_tax_id)
        results.append(vendor_res)

        # 2. Validación SQL: Detección de Factura Duplicada
        dup_res = self._validate_duplicate(invoice_data, vendor_id, existing_invoice_id)
        results.append(dup_res)

        # 3. Validación SQL: Orden de Compra (PO)
        po_id, po_res = self._validate_purchase_order(invoice_data, vendor_id)
        results.extend(po_res)

        # 4. Validación Aritmética y Cuadre Fiscal
        arith_res = self._validate_arithmetic(invoice_data)
        results.extend(arith_res)

        # Determinar estado global
        has_errors = any(not r.passed and r.severity == "ERROR" for r in results)
        has_warnings = any(not r.passed and r.severity == "WARNING" for r in results)

        if has_errors:
            overall_status = "REJECTED"
        elif has_warnings:
            overall_status = "PENDING_REVIEW"
        else:
            overall_status = "VALIDATED"

        return ValidationReport(
            overall_status=overall_status,
            vendor_id=vendor_id,
            po_id=po_id,
            results=results,
        )

    def _validate_vendor(self, tax_id: str) -> Tuple[Optional[int], RuleResult]:
        """Consulta SQL: Valida que el RFC/Tax ID exista y esté activo en el catálogo contable."""
        query = text("""
            SELECT id, name, is_active 
            FROM vendors 
            WHERE UPPER(tax_id) = :tax_id
            LIMIT 1
        """)
        row = self.db.execute(query, {"tax_id": tax_id.upper()}).fetchone()

        if not row:
            return None, RuleResult(
                rule_name="SQL_VENDOR_EXISTS",
                passed=False,
                severity="ERROR",
                message=f"El proveedor con RFC/Tax ID '{tax_id}' no está dado de alta en el sistema contable.",
            )

        vendor_id, name, is_active = row[0], row[1], bool(row[2])

        if not is_active:
            return vendor_id, RuleResult(
                rule_name="SQL_VENDOR_ACTIVE",
                passed=False,
                severity="ERROR",
                message=f"El proveedor '{name}' ({tax_id}) se encuentra BLOQUEADO / INACTIVO.",
            )

        return vendor_id, RuleResult(
            rule_name="SQL_VENDOR_VALID",
            passed=True,
            severity="INFO",
            message=f"Proveedor verificado en base de datos: {name} (ID: {vendor_id}).",
        )

    def _validate_duplicate(
        self,
        invoice_data: ExtractedInvoiceData,
        vendor_id: Optional[int],
        existing_invoice_id: Optional[int]
    ) -> RuleResult:
        """Consulta SQL: Verifica que la factura no haya sido registrada previamente."""
        # 1. Comprobar por Folio Fiscal / UUID si existe
        if invoice_data.uuid:
            query_uuid = text("""
                SELECT id, invoice_number 
                FROM invoices 
                WHERE uuid = :uuid AND (:curr_id IS NULL OR id != :curr_id)
                LIMIT 1
            """)
            dup_uuid = self.db.execute(query_uuid, {"uuid": invoice_data.uuid, "curr_id": existing_invoice_id}).fetchone()
            if dup_uuid:
                return RuleResult(
                    rule_name="SQL_DUPLICATE_CHECK",
                    passed=False,
                    severity="ERROR",
                    message=f"Factura duplicada: El UUID '{invoice_data.uuid}' ya fue registrado en la factura ID #{dup_uuid[0]}.",
                )

        # 2. Comprobar por combinación (Folio de Factura + Proveedor)
        if vendor_id:
            query_folio = text("""
                SELECT id 
                FROM invoices 
                WHERE invoice_number = :inv_num 
                  AND vendor_id = :vendor_id 
                  AND (:curr_id IS NULL OR id != :curr_id)
                LIMIT 1
            """)
            dup_folio = self.db.execute(query_folio, {
                "inv_num": invoice_data.invoice_number,
                "vendor_id": vendor_id,
                "curr_id": existing_invoice_id,
            }).fetchone()

            if dup_folio:
                return RuleResult(
                    rule_name="SQL_DUPLICATE_CHECK",
                    passed=False,
                    severity="ERROR",
                    message=f"Factura duplicada: El número '{invoice_data.invoice_number}' ya existe para este proveedor (ID #{dup_folio[0]}).",
                )

        return RuleResult(
            rule_name="SQL_DUPLICATE_CHECK",
            passed=True,
            severity="INFO",
            message="No se encontraron registros previos de esta factura en el sistema.",
        )

    def _validate_purchase_order(
        self,
        invoice_data: ExtractedInvoiceData,
        vendor_id: Optional[int]
    ) -> Tuple[Optional[int], List[RuleResult]]:
        """Consulta SQL: Valida la orden de compra asociada, moneda y tolerancia de importe."""
        results: List[RuleResult] = []

        if not invoice_data.po_number:
            # Si no trae PO, se genera advertencia contable
            results.append(
                RuleResult(
                    rule_name="SQL_PO_EXISTS",
                    passed=False,
                    severity="WARNING",
                    message="La factura no especifica una Orden de Compra (PO). Requiere autorización manual de finanzas.",
                )
            )
            return None, results

        query_po = text("""
            SELECT id, vendor_id, expected_amount, currency, status 
            FROM purchase_orders 
            WHERE po_number = :po_num
            LIMIT 1
        """)
        po_row = self.db.execute(query_po, {"po_num": invoice_data.po_number}).fetchone()

        if not po_row:
            results.append(
                RuleResult(
                    rule_name="SQL_PO_EXISTS",
                    passed=False,
                    severity="ERROR",
                    message=f"La Orden de Compra '{invoice_data.po_number}' no existe en el sistema contable.",
                )
            )
            return None, results

        po_id, po_vendor_id, expected_amount, po_currency, po_status = (
            po_row[0], po_row[1], float(po_row[2]), po_row[3], po_row[4]
        )

        # Validar coincidencia de proveedor
        if vendor_id and po_vendor_id != vendor_id:
            results.append(
                RuleResult(
                    rule_name="SQL_PO_VENDOR_MATCH",
                    passed=False,
                    severity="ERROR",
                    message=f"La OC '{invoice_data.po_number}' pertenece a otro proveedor registrado.",
                )
            )

        # Validar estado de la PO
        if po_status != "OPEN":
            results.append(
                RuleResult(
                    rule_name="SQL_PO_STATUS",
                    passed=False,
                    severity="ERROR",
                    message=f"La OC '{invoice_data.po_number}' no está abierta (Estado actual: '{po_status}').",
                )
            )

        # Validar Moneda
        if invoice_data.currency.upper() != po_currency.upper():
            results.append(
                RuleResult(
                    rule_name="SQL_PO_CURRENCY_MATCH",
                    passed=False,
                    severity="ERROR",
                    message=f"Discrepancia de moneda: Factura en '{invoice_data.currency}' vs OC en '{po_currency}'.",
                )
            )

        # Validar Tolerancia de Importe
        diff = abs(invoice_data.total_amount - expected_amount)
        pct_diff = (diff / expected_amount) * 100 if expected_amount > 0 else 100.0

        if pct_diff > self.po_tolerance:
            results.append(
                RuleResult(
                    rule_name="SQL_PO_AMOUNT_MATCH",
                    passed=False,
                    severity="ERROR",
                    message=(
                        f"Importe fuera de tolerancia: Factura (${invoice_data.total_amount:,.2f}) vs "
                        f"OC (${expected_amount:,.2f}). Variación: {pct_diff:.2f}% (Máx permitido: {self.po_tolerance}%)."
                    ),
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="SQL_PO_AMOUNT_MATCH",
                    passed=True,
                    severity="INFO",
                    message=f"Importe dentro de tolerancia: OC esperada ${expected_amount:,.2f}, Factura ${invoice_data.total_amount:,.2f}.",
                )
            )

        return po_id, results

    def _validate_arithmetic(self, invoice_data: ExtractedInvoiceData) -> List[RuleResult]:
        """Valida que los cálculos de las partidas y totales cuadren exactamente."""
        results: List[RuleResult] = []

        # 1. Suma de partidas vs Subtotal
        if invoice_data.items:
            items_sum = sum(item.total_price for item in invoice_data.items)
            if abs(items_sum - invoice_data.subtotal) > 0.10:
                results.append(
                    RuleResult(
                        rule_name="ARITHMETIC_ITEMS_VS_SUBTOTAL",
                        passed=False,
                        severity="ERROR",
                        message=f"Descuadre en partidas: Suma de conceptos (${items_sum:,.2f}) != Subtotal declarado (${invoice_data.subtotal:,.2f}).",
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_name="ARITHMETIC_ITEMS_VS_SUBTOTAL",
                        passed=True,
                        severity="INFO",
                        message="Suma de partidas coincide con el subtotal.",
                    )
                )

        # 2. Subtotal + Impuestos vs Total
        calculated_total = invoice_data.subtotal + invoice_data.tax_amount
        if abs(calculated_total - invoice_data.total_amount) > 0.10:
            results.append(
                RuleResult(
                    rule_name="ARITHMETIC_SUBTOTAL_TAX_VS_TOTAL",
                    passed=False,
                    severity="ERROR",
                    message=(
                        f"Descuadre en total: Subtotal (${invoice_data.subtotal:,.2f}) + "
                        f"IVA (${invoice_data.tax_amount:,.2f}) = ${calculated_total:,.2f}, pero el total reporta ${invoice_data.total_amount:,.2f}."
                    ),
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="ARITHMETIC_SUBTOTAL_TAX_VS_TOTAL",
                    passed=True,
                    severity="INFO",
                    message="Subtotal + Impuestos cuadra exactamente con el total.",
                )
            )

        return results

