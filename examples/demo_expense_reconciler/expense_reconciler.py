from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    date: str
    merchant: str
    amount: float
    category: str
    note: str = ""


@dataclass(frozen=True)
class BudgetAlert:
    category: str
    budget: float
    spent: float
    over_by: float


@dataclass(frozen=True)
class ReconciliationReport:
    month: str
    income: float
    spending: float
    net: float
    category_totals: dict[str, float]
    duplicate_groups: list[list[Transaction]]
    alerts: list[BudgetAlert]


def normalize_category(raw_category: str) -> str:
    raise NotImplementedError


def parse_transactions(csv_text: str) -> list[Transaction]:
    raise NotImplementedError


def monthly_summary(transactions: list[Transaction], month: str) -> dict[str, float]:
    raise NotImplementedError


def detect_duplicates(transactions: list[Transaction]) -> list[list[Transaction]]:
    raise NotImplementedError


def budget_alerts(summary: dict[str, float], budgets: dict[str, float]) -> list[BudgetAlert]:
    raise NotImplementedError


def reconcile(csv_text: str, month: str, budgets: dict[str, float]) -> ReconciliationReport:
    raise NotImplementedError
