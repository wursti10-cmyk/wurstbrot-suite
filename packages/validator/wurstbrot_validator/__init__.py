"""Structured validation for normalized Wurstbrot datamine databases."""

from .validator import (
    Finding,
    HealthReport,
    Severity,
    legacy_validation_report,
    validate_database,
    write_health_reports,
)
from .rules import (
    RULE_DEFINITIONS,
    VALIDATOR_VERSION,
    discover_tested_rules,
    render_rule_documentation,
)

__all__ = [
    "Finding",
    "HealthReport",
    "Severity",
    "legacy_validation_report",
    "validate_database",
    "write_health_reports",
    "RULE_DEFINITIONS",
    "VALIDATOR_VERSION",
    "discover_tested_rules",
    "render_rule_documentation",
]
