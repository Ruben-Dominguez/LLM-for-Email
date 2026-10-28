from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel


class InvoiceItemResponse(BaseModel):
    id: int
    description: str
    quantity: float
    unit_price: float
    total_price: float
    accounting_account_code: Optional[str] = None

    class Config:
        from_attributes = True


class ValidationLogResponse(BaseModel):
    id: int
    rule_name: str
    passed: bool
    severity: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceSummaryResponse(BaseModel):
    id: int
    invoice_number: str
    uuid: Optional[str] = None
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    po_number: Optional[str] = None
    issue_date: Optional[date] = None
    currency: str
    subtotal: float
    tax_amount: float
    total_amount: float
    status: str
    source_file: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceDetailResponse(InvoiceSummaryResponse):
    items: List[InvoiceItemResponse] = []
    validation_logs: List[ValidationLogResponse] = []

    class Config:
        from_attributes = True


class SyncEmailsResponse(BaseModel):
    processed_count: int
    invoices: List[InvoiceSummaryResponse]
    errors: List[str]


class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    llm_provider: str
    email_source: str
    timestamp: datetime
