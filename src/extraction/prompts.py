import json
from src.extraction.schemas import ExtractedInvoiceData

SYSTEM_INVOICE_EXTRACTION_PROMPT = """Eres un asistente de IA especializado en finanzas, contabilidad y auditoría fiscal.
Tu labor es analizar texto o documentos de facturas (CFDI, facturas comerciales, invoices) y extraer con precisión quirúrgica todos los datos estructurados necesarios para el sistema ERP.

REGLAS OBLIGATORIAS:
1. Extrae los valores numéricos limpios (sin símbolos de moneda, sin comas separadoras de miles).
2. Normaliza el RFC / Tax ID a mayúsculas, sin espacios ni caracteres especiales.
3. Si el documento contiene un Folio Fiscal / UUID (36 caracteres hexadecimales como 550e8400-e29b-41d4-a716-446655440000), extráelo en el campo 'uuid'.
4. Identifica explícitamente si se hace referencia a una Orden de Compra (PO, Purchase Order, OC, O.C.) y asígnala a 'po_number'.
5. Normaliza las fechas a formato estándar ISO 'YYYY-MM-DD'.
6. Para cada partida ('items'), desglosa la descripción, cantidad, precio unitario y total.
7. Devuelve EXCLUSIVAMENTE un objeto JSON válido acorde al esquema indicado, sin texto adicional, sin bloques de markdown adicionales.
"""

FEW_SHOT_EXAMPLE = """
EJEMPLO DE DOCUMENTO:
---------------------------------------------
EMISOR: Proveedor de Muestra S.A.
RFC: PMS990101AA1
Factura No: F-1234
Orden de Compra: PO-2026-099
Fecha: 15 de Octubre de 2026
Concepto: 2 Licencias de Base de Datos - Unitario: $5,000.00 - Total: $10,000.00
Subtotal: $10,000.00
IVA 16%: $1,600.00
Total a pagar: $11,600.00 MXN
---------------------------------------------

SALIDA JSON ESPERADA:
{
  "invoice_number": "F-1234",
  "uuid": null,
  "vendor_name": "Proveedor de Muestra S.A.",
  "vendor_tax_id": "PMS990101AA1",
  "po_number": "PO-2026-099",
  "issue_date": "2026-10-15",
  "currency": "MXN",
  "subtotal": 10000.00,
  "tax_amount": 1600.00,
  "total_amount": 11600.00,
  "items": [
    {
      "description": "Licencias de Base de Datos",
      "quantity": 2.0,
      "unit_price": 5000.00,
      "total_price": 10000.00,
      "suggested_category": "Software"
    }
  ],
  "confidence_score": 0.98,
  "notes": "Extracción precisa"
}
"""


def build_user_prompt(document_text: str) -> str:
    """Construye el prompt de usuario con el texto del documento y el esquema requerido."""
    schema_json = json.dumps(ExtractedInvoiceData.model_json_schema(), indent=2)
    return f"""A continuación se presenta el contenido de una factura para procesar:

=== DOCUMENTO DE FACTURA ===
{document_text}
=== FIN DEL DOCUMENTO ===

Por favor, extrae los datos y responde únicamente con un JSON que cumpla estrictamente con este esquema Pydantic:
{schema_json}
"""

