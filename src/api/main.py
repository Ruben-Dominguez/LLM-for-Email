from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.database.connection import init_db
from src.database.seed import seed_database
from src.api.routers import health, invoices


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: Inicialización de la base de datos contable."""
    init_db()
    # Sembrar base de datos si es la primera ejecución
    try:
        seed_database()
    except Exception:
        pass
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="""
### Sistema Automatizado de Ingesta, Extracción y Validación Contable de Facturas

Esta API REST transforma el proceso manual de recepción de facturas por correo:
1. **Ingesta Inteligente**: Monitorea bandejas de correo vía IMAP (o mock) y descarga facturas adjuntas en PDF/TXT.
2. **Extracción Estructurada con LLM**: Utiliza modelos de IA generativa (Gemini / OpenAI) con esquemas de Pydantic y prompt engineering para extraer datos con precisión.
3. **Clasificación Semántica (RAG)**: Asocia automáticamente los conceptos de la factura con el catálogo de cuentas contables del ERP.
4. **Validación Contable (SQL)**: Comprueba reglas de negocio contables contra la base de datos (proveedor activo, no duplicidad, orden de compra y sumas aritméticas).
5. **Auditoría y Exportación**: Registra logs detallados de cada regla SQL y permite exportar reportes directos en Microsoft Excel (.xlsx).
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuración de CORS para integración con paneles frontend o ERPs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas bajo el prefijo configurado (default: /api/v1)
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(invoices.router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Bienvenido a {settings.PROJECT_NAME}",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }
