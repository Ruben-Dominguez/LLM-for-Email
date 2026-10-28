from dataclasses import dataclass
from typing import List


@dataclass
class RuleResult:
    """Resultado individual de una regla de validación contable."""
    rule_name: str
    passed: bool
    severity: str  # ERROR, WARNING, INFO
    message: str


@dataclass
class ValidationReport:
    """Informe consolidado de validación contable."""
    overall_status: str  # VALIDATED, PENDING_REVIEW, REJECTED
    vendor_id: int | None
    po_id: int | None
    results: List[RuleResult]

    @property
    def has_errors(self) -> bool:
        return any(not r.passed and r.severity == "ERROR" for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(not r.passed and r.severity == "WARNING" for r in self.results)
