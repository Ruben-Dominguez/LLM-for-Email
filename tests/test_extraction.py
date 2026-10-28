from src.extraction.extractor import MockInvoiceExtractor
from src.extraction.schemas import ExtractedInvoiceData


def test_mock_extractor_valid_invoice():
    sample_text = """
    EMISOR:
    Razón Social: Tech Solutions & Cloud Services S.A. de C.V.
    RFC: TSO150210XYZ
    Número de Factura: FAC-2026-901
    Folio Fiscal (UUID): 550e8400-e29b-41d4-a716-446655440001
    Orden de Compra: PO-2026-101
    Fecha de Emisión: 2026-10-25
    Moneda: MXN

    1.00 | Licencias anuales de software ERP en la nube | $20,000.00 | $20,000.00

    SUBTOTAL: $20,000.00
    IVA: $3,200.00
    TOTAL: $23,200.00
    """
    extractor = MockInvoiceExtractor()
    extracted: ExtractedInvoiceData = extractor.extract_from_text(sample_text)

    assert extracted.invoice_number == "FAC-2026-901"
    assert extracted.vendor_tax_id == "TSO150210XYZ"
    assert extracted.uuid == "550e8400-e29b-41d4-a716-446655440001"
    assert extracted.po_number == "PO-2026-101"
    assert extracted.subtotal == 20000.0
    assert extracted.tax_amount == 3200.0
    assert extracted.total_amount == 23200.0
    assert len(extracted.items) == 1
    assert extracted.items[0].quantity == 1.0
    assert extracted.items[0].unit_price == 20000.0

