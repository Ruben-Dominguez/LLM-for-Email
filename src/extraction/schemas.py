from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractedInvoiceItem(BaseModel):
    """Partida individual extraída por el LLM."""
    description: str = Field(..., description="Descripción detallada del producto o servicio.")
    quantity: float = Field(default=1.0, description="Cantidad adquirida.")
    unit_price: float = Field(..., description="Precio unitario antes de impuestos.")
    total_price: float = Field(..., description="Importe total de la partida (cantidad * precio unitario).")
    suggested_category: Optional[str] = Field(None, description="Categoría de gasto sugerida por el LLM.")


class ExtractedInvoiceData(BaseModel):
    """Estructura normalizada y validada por Pydantic para facturas extraídas."""
    invoice_number: str = Field(..., description="Número, serie o folio de la factura.")
    uuid: Optional[str] = Field(None, description="Folio Fiscal / UUID digital si existe.")
    vendor_name: str = Field(..., description="Nombre o Razón Social del proveedor emisor.")
    vendor_tax_id: str = Field(..., description="Identificación fiscal del emisor (RFC, NIF, CIF, Tax ID) en mayúsculas sin guiones.")
    po_number: Optional[str] = Field(None, description="Número de Orden de Compra (PO) asociada si está indicada.")
    issue_date: Optional[str] = Field(None, description="Fecha de emisión en formato YYYY-MM-DD.")
    currency: str = Field(default="MXN", description="Código de moneda ISO (ej. MXN, USD, EUR).")
    subtotal: float = Field(..., description="Subtotal antes de impuestos y retenciones.")
    tax_amount: float = Field(default=0.0, description="Importe total de impuestos trasladados (ej. IVA).")
    total_amount: float = Field(..., description="Importe total final a pagar.")
    items: List[ExtractedInvoiceItem] = Field(default_factory=list, description="Lista de partidas o conceptos de la factura.")
    confidence_score: float = Field(default=0.95, description="Puntuación de confianza estimada por el modelo (0.0 a 1.0).")
    notes: Optional[str] = Field(None, description="Observaciones o notas de discrepancia detectadas.")
