import sys
import os
from pathlib import Path

# Configurar directorio raíz del proyecto para importar src y config
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Asegurar indicador de entorno Serverless
os.environ.setdefault("VERCEL", "1")

from src.api.main import app
