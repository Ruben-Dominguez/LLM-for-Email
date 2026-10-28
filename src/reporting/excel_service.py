import io
from datetime import datetime
from typing import List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.database.models import Invoice


class ExcelReportingService:
    """Servicio de generación y lectura de reportes Excel corporativos usando openpyxl."""

    @staticmethod
    def generate_invoices_report(invoices: List[Invoice]) -> bytes:
        """Genera un archivo Excel (.xlsx) estilizado con el consolidado y auditoría de facturas."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Validación de Facturas"

        # Paleta de colores corporativos
        HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        REGULAR_FONT = Font(name="Calibri", size=10)
        BOLD_FONT = Font(name="Calibri", size=10, bold=True)

        STATUS_STYLES = {
            "VALIDATED": {
                "fill": PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid"),
                "font": Font(name="Calibri", size=10, bold=True, color="375623"),
            },
            "PENDING_REVIEW": {
                "fill": PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),
                "font": Font(name="Calibri", size=10, bold=True, color="7F6000"),
            },
            "REJECTED": {
                "fill": PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid"),
                "font": Font(name="Calibri", size=10, bold=True, color="C65911"),
            },
        }

        THIN_BORDER = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )

        # Encabezados
        headers = [
            "ID",
            "Folio Factura",
            "UUID / Folio Fiscal",
            "RFC Proveedor",
            "Proveedor",
            "Orden de Compra",
            "Fecha Emisión",
            "Moneda",
            "Subtotal",
            "IVA / Impuestos",
            "Total",
            "Estado Validación",
            "Detalle Auditoría SQL",
        ]

        ws.append(headers)

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Filas de datos
        for row_idx, inv in enumerate(invoices, start=2):
            vendor_rfc = inv.vendor.tax_id if inv.vendor else "DESCONOCIDO"
            vendor_name = inv.vendor.name if inv.vendor else "No registrado"
            po_num = inv.purchase_order.po_number if inv.purchase_order else "N/A"

            # Resumen de logs de auditoría
            log_messages = "; ".join(
                [f"[{l.rule_name}]: {l.message}" for l in inv.validation_logs if not l.passed]
            ) or "Todas las reglas contables aprobadas"

            row_data = [
                inv.id,
                inv.invoice_number,
                inv.uuid or "N/A",
                vendor_rfc,
                vendor_name,
                po_num,
                inv.issue_date.strftime("%Y-%m-%d") if inv.issue_date else "N/A",
                inv.currency,
                inv.subtotal,
                inv.tax_amount,
                inv.total_amount,
                inv.status,
                log_messages,
            ]
            ws.append(row_data)

            # Estilos de celdas
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = REGULAR_FONT
                cell.border = THIN_BORDER

                # Formatos de número para moneda
                if col_idx in (9, 10, 11):
                    cell.number_format = '$#,##0.00'
                    cell.alignment = Alignment(horizontal="right")
                elif col_idx in (1, 7, 8):
                    cell.alignment = Alignment(horizontal="center")

                # Estilo condicional para el estado
                if col_idx == 12:
                    style = STATUS_STYLES.get(inv.status)
                    if style:
                        cell.fill = style["fill"]
                        cell.font = style["font"]
                    cell.alignment = Alignment(horizontal="center")

        # Ajuste automático del ancho de columnas
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
