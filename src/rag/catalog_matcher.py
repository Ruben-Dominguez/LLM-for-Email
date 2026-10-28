import math
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from src.database.models import AccountingAccount


class SemanticCatalogMatcher:
    """Módulo RAG / Embeddings liviano para clasificación contable.

    Mapea descripciones libres de productos/servicios en las facturas hacia
    el catálogo de cuentas contables del ERP mediante similitud de coseno
    y ponderación semántica de términos.
    """

    def __init__(self, db: Session):
        self.db = db
        self._accounts: List[AccountingAccount] = []
        self._account_vectors: Dict[str, Dict[str, float]] = {}
        self._load_accounts()

    def _load_accounts(self) -> None:
        """Carga las cuentas contables desde la base de datos y genera sus representaciones vectoriales."""
        self._accounts = self.db.query(AccountingAccount).all()
        for acc in self._accounts:
            # Unir nombre, categoría y palabras clave
            corpus = f"{acc.name} {acc.category} {acc.keywords or ''}".lower()
            tokens = self._tokenize(corpus)
            self._account_vectors[acc.code] = self._term_frequencies(tokens)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Limpia y tokeniza texto en palabras clave normalizadas."""
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        stopwords = {
            "de", "la", "el", "los", "las", "un", "una", "unos", "y", "en", "para",
            "por", "con", "del", "al", "a", "o", "u", "este", "esta", "que", "se"
        }
        tokens = [t for t in clean.split() if len(t) > 2 and t not in stopwords]
        return tokens

    @staticmethod
    def _term_frequencies(tokens: List[str]) -> Dict[str, float]:
        """Calcula el vector de frecuencia de términos."""
        freq: Dict[str, float] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0.0) + 1.0
        # Normalizar vector
        norm = math.sqrt(sum(v * v for v in freq.values()))
        if norm > 0:
            for k in freq:
                freq[k] /= norm
        return freq

    @staticmethod
    def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Calcula la similitud de coseno entre dos vectores densos/dispersos."""
        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
        return dot_product

    def match_item(self, item_description: str) -> Tuple[Optional[str], float]:
        """Encuentra la cuenta contable más similar para la descripción de un producto.

        Retorna:
            (accounting_account_code, similarity_score)
        """
        if not self._account_vectors:
            self._load_accounts()

        item_tokens = self._tokenize(item_description)
        item_vector = self._term_frequencies(item_tokens)

        best_code: Optional[str] = None
        best_score: float = 0.0

        for code, acc_vector in self._account_vectors.items():
            score = self._cosine_similarity(item_vector, acc_vector)
            if score > best_score:
                best_score = score
                best_code = code

        # Si no hubo coincidencia semántica relevante (umbral mínimo)
        if best_score < 0.1:
            return None, best_score

        return best_code, round(best_score, 4)
