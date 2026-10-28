from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Date,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Vendor(Base):
    """Proveedor registrado en el sistema contable / ERP."""
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tax_id = Column(String(50), unique=True, index=True, nullable=False)  # RFC / NIF / Tax ID
    name = Column(String(200), nullable=False)
    contact_email = Column(String(100), nullable=True)
    payment_terms_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    invoices = relationship("Invoice", back_populates="vendor")


class PurchaseOrder(Base):
    """Orden de Compra aprobada por el área financiera."""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "PO-2026-001"
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    expected_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="MXN", nullable=False)
    status = Column(String(20), default="OPEN", nullable=False)  # OPEN, FULFILLED, CANCELLED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vendor = relationship("Vendor", back_populates="purchase_orders")
    invoices = relationship("Invoice", back_populates="purchase_order")


class AccountingAccount(Base):
    """Catálogo de cuentas contables del ERP para clasificación y RAG."""
    __tablename__ = "accounting_accounts"

    code = Column(String(30), primary_key=True)  # e.g., "601.01"
    name = Column(String(200), nullable=False)  # e.g., "Servicios de Nube y Software"
    category = Column(String(100), nullable=False)  # e.g., "Gastos Operativos"
    keywords = Column(Text, nullable=True)  # e.g., "software, hosting, cloud, licencias, saas"


class Invoice(Base):
    """Factura extraída y registrada en el sistema."""
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String(100), index=True, nullable=False)
    uuid = Column(String(100), unique=True, index=True, nullable=True)  # Folio Fiscal / UUID
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=True)
    
    issue_date = Column(Date, nullable=True)
    currency = Column(String(10), default="MXN", nullable=False)
    subtotal = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)

    # Estado de validación contable
    status = Column(String(30), default="PENDING_REVIEW", index=True, nullable=False)  # VALIDATED, PENDING_REVIEW, REJECTED
    source_file = Column(String(255), nullable=True)
    extracted_raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    vendor = relationship("Vendor", back_populates="invoices")
    purchase_order = relationship("PurchaseOrder", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    validation_logs = relationship("ValidationLog", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    """Partida individual o concepto dentro de la factura."""
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String(300), nullable=False)
    quantity = Column(Float, default=1.0, nullable=False)
    unit_price = Column(Float, default=0.0, nullable=False)
    total_price = Column(Float, default=0.0, nullable=False)
    accounting_account_code = Column(String(30), ForeignKey("accounting_accounts.code"), nullable=True)

    invoice = relationship("Invoice", back_populates="items")
    accounting_account = relationship("AccountingAccount")


class ValidationLog(Base):
    """Registro de auditoría de cada regla de validación SQL ejecutada."""
    __tablename__ = "validation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    rule_name = Column(String(100), nullable=False)  # e.g., "VENDOR_EXISTS", "PO_MATCH", "ARITHMETIC_CHECK"
    passed = Column(Boolean, nullable=False)
    severity = Column(String(20), default="ERROR", nullable=False)  # ERROR, WARNING, INFO
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoice = relationship("Invoice", back_populates="validation_logs")
