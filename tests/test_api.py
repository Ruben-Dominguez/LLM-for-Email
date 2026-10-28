import io
import uuid
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.database.connection import init_db, engine
from src.database.models import Base
from src.database.seed import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Inicializa y siembra la base de datos limpia para la suite de pruebas de la API."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    seed_database()


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("HEALTHY", "DEGRADED")
        assert data["database_connected"] is True


def test_sync_mock_emails():
    with TestClient(app) as client:
        response = client.post("/api/v1/invoices/sync-emails?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "processed_count" in data
        assert data["processed_count"] >= 1
        assert len(data["invoices"]) >= 1


def test_list_invoices():
    with TestClient(app) as client:
        response = client.get("/api/v1/invoices")
        assert response.status_code == 200
        invoices = response.json()
        assert isinstance(invoices, list)
        assert len(invoices) >= 1


def test_get_invoice_detail_and_revalidate():
    with TestClient(app) as client:
        # 1. Obtener primera factura existente
        list_resp = client.get("/api/v1/invoices?limit=1")
        invoices = list_resp.json()
        assert len(invoices) > 0
        inv_id = invoices[0]["id"]

        # 2. Consultar detalle
        detail_resp = client.get(f"/api/v1/invoices/{inv_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == inv_id
        assert "validation_logs" in detail
        assert "items" in detail

        # 3. Revalidar factura
        reval_resp = client.post(f"/api/v1/invoices/{inv_id}/revalidate")
        assert reval_resp.status_code == 200
        assert reval_resp.json()["id"] == inv_id


def test_upload_invoice_file():
    with TestClient(app) as client:
        unique_uuid = str(uuid.uuid4())
        invoice_content = f"""
        EMISOR:
        Razon Social: Tech Solutions & Cloud Services S.A. de C.V.
        RFC: TSO150210XYZ
        Numero de Factura: FAC-UPLOAD-001
        Folio Fiscal (UUID): {unique_uuid}
        Orden de Compra: PO-2026-101
        Fecha de Emision: 2026-10-28
        Moneda: MXN

        1.00 | Servicios de infraestructura Cloud | $20000.00 | $20000.00

        SUBTOTAL: $20000.00
        IVA: $3200.00
        TOTAL: $23200.00
        """.encode("utf-8")

        files = {
            "file": ("factura_upload.txt", io.BytesIO(invoice_content), "text/plain")
        }
        response = client.post("/api/v1/invoices/upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_number"] == "FAC-UPLOAD-001"
        assert data["status"] == "VALIDATED"


def test_export_excel():
    with TestClient(app) as client:
        response = client.get("/api/v1/invoices/export/excel")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(response.content) > 1000  # Archivo binario Excel con contenido


def test_dashboard_frontend():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "AutoInvoice" in response.text


def test_invoice_stats():
    with TestClient(app) as client:
        response = client.get("/api/v1/invoices/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_invoices" in data
        assert "validated_count" in data
        assert "rejected_count" in data
        assert "approval_rate" in data


def test_samples_and_direct_processing():
    with TestClient(app) as client:
        samples_resp = client.get("/api/v1/invoices/samples")
        assert samples_resp.status_code == 200
        samples = samples_resp.json()
        assert len(samples) > 0

        # Probar procesamiento directo de la muestra tech válida
        process_resp = client.post("/api/v1/invoices/samples/factura_valida_tech.txt/process")
        assert process_resp.status_code == 200
        data = process_resp.json()
        assert data["invoice_number"] == "FAC-2026-901"
        assert data["status"] in ("VALIDATED", "REJECTED")
