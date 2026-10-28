import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Vendor, PurchaseOrder
from src.extraction.schemas import ExtractedInvoiceData, ExtractedInvoiceItem
from src.validation.validator import InvoiceSQLValidator


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create active vendor
    v1 = Vendor(
        tax_id="TSO150210XYZ",
        name="Tech Solutions S.A.",
        is_active=True,
    )
    # Create inactive vendor
    v2 = Vendor(
        tax_id="INA000101ZZZ",
        name="Proveedor Inactivo S.A.",
        is_active=False,
    )
    db.add_all([v1, v2])
    db.flush()

    # Create open PO
    po = PurchaseOrder(
        po_number="PO-2026-101",
        vendor_id=v1.id,
        expected_amount=23200.0,
        currency="MXN",
        status="OPEN",
    )
    db.add(po)
    db.commit()

    yield db
    db.close()


def test_validation_successful_invoice(memory_db):
    validator = InvoiceSQLValidator(memory_db)
    invoice_data = ExtractedInvoiceData(
        invoice_number="FAC-100",
        uuid="550e8400-e29b-41d4-a716-446655440099",
        vendor_name="Tech Solutions S.A.",
        vendor_tax_id="TSO150210XYZ",
        po_number="PO-2026-101",
        issue_date="2026-10-28",
        currency="MXN",
        subtotal=20000.0,
        tax_amount=3200.0,
        total_amount=23200.0,
        items=[
            ExtractedInvoiceItem(
                description="Servicio Cloud",
                quantity=1.0,
                unit_price=20000.0,
                total_price=20000.0,
            )
        ],
    )

    report = validator.validate(invoice_data)
    assert report.overall_status == "VALIDATED"
    assert not report.has_errors


def test_validation_unregistered_vendor(memory_db):
    validator = InvoiceSQLValidator(memory_db)
    invoice_data = ExtractedInvoiceData(
        invoice_number="FAC-200",
        vendor_name="Fantasma",
        vendor_tax_id="NO_EXISTO_RFC",
        currency="MXN",
        subtotal=1000.0,
        tax_amount=160.0,
        total_amount=1160.0,
    )

    report = validator.validate(invoice_data)
    assert report.overall_status == "REJECTED"
    assert any(r.rule_name == "SQL_VENDOR_EXISTS" and not r.passed for r in report.results)


def test_validation_arithmetic_error(memory_db):
    validator = InvoiceSQLValidator(memory_db)
    invoice_data = ExtractedInvoiceData(
        invoice_number="FAC-300",
        vendor_name="Tech Solutions S.A.",
        vendor_tax_id="TSO150210XYZ",
        po_number="PO-2026-101",
        currency="MXN",
        subtotal=20000.0,
        tax_amount=3200.0,
        total_amount=99999.0,  # Descuadre evidente
    )

    report = validator.validate(invoice_data)
    assert report.overall_status == "REJECTED"
    assert any("ARITHMETIC" in r.rule_name and not r.passed for r in report.results)

