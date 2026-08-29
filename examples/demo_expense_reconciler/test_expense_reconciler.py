import pytest

from expense_reconciler import (
    BudgetAlert,
    ReconciliationReport,
    Transaction,
    budget_alerts,
    detect_duplicates,
    monthly_summary,
    normalize_category,
    parse_transactions,
    reconcile,
)


CSV_TEXT = """date,merchant,amount,category,note
2026-08-01,Acme Payroll,5000.00,Income,monthly salary
2026-08-02,Fresh Mart,-89.35,Groceries,weekly food
2026-08-03,Metro,-3.50,transport,subway
2026-08-03,Metro,-3.50,Transport,subway retry
2026-08-08,Book Store,-45.00,education,python book
2026-08-12,Fresh Mart,-112.15,food,party dinner
2026-09-01,Fresh Mart,-30.00,food,next month
"""


def test_normalize_category_handles_aliases_and_spacing() -> None:
    assert normalize_category(" food ") == "groceries"
    assert normalize_category("Groceries") == "groceries"
    assert normalize_category("transport") == "transport"
    assert normalize_category("TRANSIT") == "transport"
    assert normalize_category("Education") == "education"
    assert normalize_category("unknown tag") == "unknown tag"


def test_parse_transactions_converts_rows_and_categories() -> None:
    transactions = parse_transactions(CSV_TEXT)

    assert len(transactions) == 7
    assert transactions[0] == Transaction(
        date="2026-08-01",
        merchant="Acme Payroll",
        amount=5000.0,
        category="income",
        note="monthly salary",
    )
    assert transactions[5].category == "groceries"
    assert transactions[6].date == "2026-09-01"


def test_parse_transactions_rejects_missing_columns() -> None:
    with pytest.raises(ValueError):
        parse_transactions("date,merchant,amount\n2026-08-01,A,-1")


def test_parse_transactions_rejects_bad_amount() -> None:
    with pytest.raises(ValueError):
        parse_transactions("date,merchant,amount,category\n2026-08-01,A,abc,food")


def test_monthly_summary_uses_abs_spending_and_ignores_other_months() -> None:
    transactions = parse_transactions(CSV_TEXT)

    summary = monthly_summary(transactions, "2026-08")

    assert summary == {
        "income": 5000.0,
        "groceries": 201.5,
        "transport": 7.0,
        "education": 45.0,
    }


def test_detect_duplicates_groups_exact_transaction_matches_after_normalization() -> None:
    transactions = parse_transactions(CSV_TEXT)

    groups = detect_duplicates(transactions)

    assert len(groups) == 1
    assert [item.merchant for item in groups[0]] == ["Metro", "Metro"]
    assert [item.note for item in groups[0]] == ["subway", "subway retry"]


def test_budget_alerts_reports_only_overspent_categories_sorted_by_overage() -> None:
    summary = {"income": 5000.0, "groceries": 201.5, "transport": 7.0, "education": 45.0}
    budgets = {"groceries": 180.0, "transport": 20.0, "education": 30.0}

    alerts = budget_alerts(summary, budgets)

    assert alerts == [
        BudgetAlert(category="groceries", budget=180.0, spent=201.5, over_by=21.5),
        BudgetAlert(category="education", budget=30.0, spent=45.0, over_by=15.0),
    ]


def test_reconcile_builds_complete_report() -> None:
    report = reconcile(CSV_TEXT, "2026-08", {"groceries": 180.0, "transport": 20.0, "education": 30.0})

    assert isinstance(report, ReconciliationReport)
    assert report.month == "2026-08"
    assert report.income == 5000.0
    assert report.spending == 253.5
    assert report.net == 4746.5
    assert report.category_totals["groceries"] == 201.5
    assert len(report.duplicate_groups) == 1
    assert [alert.category for alert in report.alerts] == ["groceries", "education"]
