from datetime import datetime, timezone
from src.database.connection import SessionLocal, init_db
from src.database.models import Vendor, PurchaseOrder, AccountingAccount


def seed_database() -> None:
    """Inserta datos contables iniciales para validar las facturas."""
    init_db()
    db = SessionLocal()

    try:
        # 1. Catálogo de Cuentas Contables (Chart of Accounts)
        accounts_data = [
            AccountingAccount(
                code="601.01",
                name="Software, Licencias y Servicios Cloud",
                category="Gastos de Tecnología",
                keywords="software cloud saas hosting licencia desarrollo servidor api nube",
            ),
            AccountingAccount(
                code="601.02",
                name="Suministros de Oficina y Papelería",
                category="Gastos Administrativos",
                keywords="papeleria hojas plumas toner suministros oficina impresiones",
            ),
            AccountingAccount(
                code="601.03",
                name="Logística, Fletes y Transporte",
                category="Costos Operativos",
                keywords="flete transporte envio paqueteria logistica aduana fletes",
            ),
            AccountingAccount(
                code="601.04",
                name="Consultoría y Servicios Profesionales",
                category="Servicios Externos",
                keywords="consultoria auditoria asesoria legal contable honorarios servicios",
            ),
        ]

        for acc in accounts_data:
            existing = db.query(AccountingAccount).filter_by(code=acc.code).first()
            if not existing:
                db.add(acc)

        db.commit()

        # 2. Proveedores autorizados
        vendors_data = [
            Vendor(
                tax_id="TSO150210XYZ",
                name="Tech Solutions & Cloud Services S.A. de C.V.",
                contact_email="facturacion@techsolutions.mx",
                payment_terms_days=30,
                is_active=True,
            ),
            Vendor(
                tax_id="PSO041120AB1",
                name="Papelería y Suministros Corporativos del Centro",
                contact_email="cobranza@suministroscentro.com",
                payment_terms_days=15,
                is_active=True,
            ),
            Vendor(
                tax_id="LTG190824LK9",
                name="Logística y Transportes Globales Express S.A.",
                contact_email="cuentasporcobrar@logisticaexpress.com",
                payment_terms_days=45,
                is_active=True,
            ),
            Vendor(
                tax_id="INA000101ZZZ",
                name="Proveedor Inactivo y Bloqueado S.A.",
                contact_email="contacto@inactivo.com",
                payment_terms_days=0,
                is_active=False,  # Proveedor bloqueado para pruebas de rechazo
            ),
        ]

        vendors_map = {}
        for v in vendors_data:
            existing = db.query(Vendor).filter_by(tax_id=v.tax_id).first()
            if not existing:
                db.add(v)
                db.flush()
                vendors_map[v.tax_id] = v
            else:
                vendors_map[v.tax_id] = existing

        db.commit()

        # 3. Órdenes de Compra (POs)
        v_tech = vendors_map["TSO150210XYZ"]
        v_papeleria = vendors_map["PSO041120AB1"]
        v_logistica = vendors_map["LTG190824LK9"]

        po_data = [
            PurchaseOrder(
                po_number="PO-2026-101",
                vendor_id=v_tech.id,
                expected_amount=23200.00,  # 20,000 subtotal + 3,200 IVA
                currency="MXN",
                status="OPEN",
            ),
            PurchaseOrder(
                po_number="PO-2026-102",
                vendor_id=v_papeleria.id,
                expected_amount=5800.00,  # 5,000 subtotal + 800 IVA
                currency="MXN",
                status="OPEN",
            ),
            PurchaseOrder(
                po_number="PO-2026-103",
                vendor_id=v_logistica.id,
                expected_amount=11600.00,
                currency="MXN",
                status="FULFILLED",  # Ya liquidada para probar rechazo por PO no abierta
            ),
        ]

        for po in po_data:
            existing = db.query(PurchaseOrder).filter_by(po_number=po.po_number).first()
            if not existing:
                db.add(po)

        db.commit()
        print("[OK] Base de datos sembrada con exito: Cuentas contables, Proveedores y Ordenes de Compra.")

    except Exception as e:
        db.rollback()
        print(f"Error al sembrar la base de datos: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
