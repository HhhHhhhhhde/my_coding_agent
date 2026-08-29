# Demo: Expense Reconciler

This is a deliberately incomplete example for testing the coding agent in build mode.

## Task

Implement the core functions in `expense_reconciler.py` and make the tests pass.

The module should parse CSV transaction records, normalize categories, summarize monthly expenses, detect duplicate transactions, compare expenses with budgets, and produce a reconciliation report.

## Constraints

- Do not add third-party dependencies.
- Keep the public function names and dataclass fields unchanged.
- Treat income as positive amounts and expenses as negative amounts.
- Duplicate detection should be conservative: same date, merchant, amount, and category.
- Invalid input should raise `ValueError` with a useful message.

## Suggested Agent Command

```bash
uv run python -m mini_agent --workspace examples/demo_expense_reconciler --max-steps 30 "请实现这个费用对账示例中的核心函数，并让当前目录下的测试通过。"
```

## Verification

```bash
uv run --extra dev pytest -q examples/demo_expense_reconciler
```
