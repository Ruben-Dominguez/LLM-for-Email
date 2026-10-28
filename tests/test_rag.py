import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, AccountingAccount
from src.rag.catalog_matcher import SemanticCatalogMatcher


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Insert sample chart of accounts
    db.add(AccountingAccount(
        code="601.01",
        name="Software, Licencias y Servicios Cloud",
        category="Gastos de Tecnología",
        keywords="software cloud saas hosting licencia desarrollo servidor api nube",
    ))
    db.add(AccountingAccount(
        code="601.02",
        name="Suministros de Oficina y Papelería",
        category="Gastos Administrativos",
        keywords="papeleria hojas plumas toner suministros oficina impresiones",
    ))
    db.commit()
    yield db
    db.close()


def test_semantic_catalog_matcher(memory_db):
    matcher = SemanticCatalogMatcher(memory_db)

    # 1. Match software related description
    code_software, score_software = matcher.match_item("Renovación de licencias anuales de software en la nube")
    assert code_software == "601.01"
    assert score_software > 0.1

    # 2. Match office stationery description
    code_office, score_office = matcher.match_item("50 cajas de hojas de papel bond para oficina")
    assert code_office == "601.02"
    assert score_office > 0.1

