"""
Month 4 — Expectation Suite: fact_sales

Target: retaildw_dq.warehouse.fact_sales
Rows:   ~500,050 (500,000 original + 50 D7 orphan inserts)

Defects injected in this table (predicted FAIL expectations in parens):
    D7  Consistency  50 rows orphan customer_key      (#18)
    D8  Validity    100 rows quantity = -1            (#11)

Coverage:
    Completeness: 6 expectations
    Uniqueness:   2 expectations
    Validity:    10 expectations
    Consistency:  4 expectations  (cross-table FK checks)
    Accuracy:     2 expectations  (arithmetic invariants)

Total: 24 expectations (predicted 22 PASS / 2 FAIL).

KEY DESIGN DECISIONS:
* Arithmetic checks (net_revenue, gross_profit) use ABS(diff) > 0.01
  tolerance rather than exact equality — defensive against float rounding.
* Revenue/profit range checks allow NEGATIVE minimums — real-world sales
  at a loss are legitimate (clearance, loss-leaders). See profile row 5.1.9.
* Cross-table FK checks use LEFT JOIN IS NULL pattern, the idiomatic
  GX 1.x way to express referential integrity.

Author: Diluksha Perera
"""

from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe


SUITE_NAME = "fact_sales_suite"


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # ------------------------------------------------------------
    # 1 & 2 — Whole-table invariants
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(
            min_value=450_000,
            max_value=550_000,
            meta={
                "dimension": "Validity",
                "rationale": "~500,050 rows expected (500K original + 50 D7 inserts); buffer for normal variance",
            },
        )
    )

    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchOrderedList(
            column_list=[
                "sales_key", "date_key", "customer_key", "product_key", "store_key",
                "order_id", "order_line_num", "quantity", "unit_price", "unit_cost",
                "discount_amount", "net_revenue", "gross_profit", "tax_amount",
            ],
            meta={
                "dimension": "Validity",
                "rationale": "Schema drift guard; 14 columns must appear in declared order",
            },
        )
    )

    # ------------------------------------------------------------
    # 3-8 — Completeness (6 expectations)
    # ------------------------------------------------------------

    for col, rationale in [
        ("sales_key", "Surrogate PK — structurally required"),
        ("date_key", "Time dimension FK — required for all temporal analysis"),
        ("customer_key", "Customer FK — required for customer analytics"),
        ("product_key", "Product FK — required for product analytics"),
        ("store_key", "Store FK — required for channel analytics"),
        ("net_revenue", "Primary revenue measure — required for all financial reports"),
    ]:
        suite.add_expectation(
            gxe.ExpectColumnValuesToNotBeNull(
                column=col,
                meta={"dimension": "Completeness", "rationale": rationale},
            )
        )

    # ------------------------------------------------------------
    # 9 — Uniqueness: surrogate PK
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="sales_key",
            meta={
                "dimension": "Uniqueness",
                "rationale": "sales_key is the surrogate PK; must be globally unique",
            },
        )
    )

    # ------------------------------------------------------------
    # 10 — Uniqueness: compound (order_id, order_line_num)
    # ------------------------------------------------------------
    # SQL-based because we want to catch duplicate order-line combos explicitly.

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT order_id, order_line_num, COUNT(*) AS dup_count "
                "FROM {batch} "
                "GROUP BY order_id, order_line_num "
                "HAVING COUNT(*) > 1"
            ),
            description="Compound (order_id, order_line_num) must be unique",
            meta={
                "dimension": "Uniqueness",
                "rationale": "Business rule: one line per (order, line#); dup = double-count risk",
            },
        )
    )

    # ------------------------------------------------------------
    # 11 — Validity: quantity must be >= 1 (no zero or negative sales)
    # ------------------------------------------------------------
    # D8 injects quantity = -1 on 100 rows → this FAILS (intended).

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="quantity",
            min_value=1,
            max_value=10000,
            meta={
                "dimension": "Validity",
                "rationale": "Sales quantity must be positive; returns should be separate rows with explicit type",
                "predicted": "FAIL — D8 injection (100 rows, quantity = -1)",
            },
        )
    )

    # ------------------------------------------------------------
    # 12-14 — Validity: price/cost/discount ranges
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="unit_price",
            min_value=0.01,
            max_value=100000,
            meta={"dimension": "Validity",
                  "rationale": "Unit price must be positive; upper bound catches encoding bugs"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="unit_cost",
            min_value=0,
            max_value=100000,
            meta={"dimension": "Validity",
                  "rationale": "Unit cost >= 0; zero allowed (promotional/complimentary goods)"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="discount_amount",
            min_value=0,
            max_value=50000,
            meta={"dimension": "Validity",
                  "rationale": "Discount must be non-negative; upper bound catches encoding bugs"},
        )
    )

    # ------------------------------------------------------------
    # 15-17 — Validity: revenue/profit/tax ranges (allow negatives for losses)
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="net_revenue",
            min_value=-10000,
            max_value=10_000_000,
            meta={
                "dimension": "Validity",
                "rationale": "Net revenue can be slightly negative if discount > (qty*price); wide upper bound",
            },
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="gross_profit",
            min_value=-10000,
            max_value=10_000_000,
            meta={
                "dimension": "Validity",
                "rationale": "Gross profit can be negative on loss-leader sales (profile row 5.1.9 confirmed this)",
            },
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="tax_amount",
            min_value=0,
            max_value=100000,
            meta={"dimension": "Validity",
                  "rationale": "Tax must be non-negative"},
        )
    )

    # ------------------------------------------------------------
    # 18-21 — Consistency: cross-table FK referential integrity
    # ------------------------------------------------------------
    # Pattern: LEFT JOIN from fact_sales to dim_X, find rows where
    # dim_X.X_key IS NULL after the join (= orphaned FK).

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT f.sales_key, f.customer_key "
                "FROM {batch} f "
                "LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key "
                "WHERE c.customer_key IS NULL"
            ),
            description="fact_sales.customer_key must reference dim_customer.customer_key",
            meta={
                "dimension": "Consistency",
                "rationale": "Referential integrity: every fact row must have a matching customer dimension",
                "predicted": "FAIL — D7 injection (50 orphan rows with customer_key = 999999)",
            },
        )
    )

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT f.sales_key, f.product_key "
                "FROM {batch} f "
                "LEFT JOIN warehouse.dim_product p ON f.product_key = p.product_key "
                "WHERE p.product_key IS NULL"
            ),
            description="fact_sales.product_key must reference dim_product.product_key",
            meta={"dimension": "Consistency",
                  "rationale": "Referential integrity: every fact row must have a matching product dimension"},
        )
    )

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT f.sales_key, f.store_key "
                "FROM {batch} f "
                "LEFT JOIN warehouse.dim_store s ON f.store_key = s.store_key "
                "WHERE s.store_key IS NULL"
            ),
            description="fact_sales.store_key must reference dim_store.store_key",
            meta={"dimension": "Consistency",
                  "rationale": "Referential integrity: every fact row must have a matching store dimension"},
        )
    )

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT f.sales_key, f.date_key "
                "FROM {batch} f "
                "LEFT JOIN warehouse.dim_date d ON f.date_key = d.date_key "
                "WHERE d.date_key IS NULL"
            ),
            description="fact_sales.date_key must reference dim_date.date_key",
            meta={"dimension": "Consistency",
                  "rationale": "Referential integrity: every fact row must have a matching date dimension"},
        )
    )

    # ------------------------------------------------------------
    # 22 & 23 — Accuracy: arithmetic invariants with 0.01 tolerance
    # ------------------------------------------------------------
    # Tolerance-based because floating-point conversion round-trips
    # (Python Decimal <-> PostgreSQL numeric) can introduce sub-cent drift.
    # Exact equality would cause false positives; 0.01 is a "1 cent" tolerance.

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT sales_key, quantity, unit_price, discount_amount, net_revenue "
                "FROM {batch} "
                "WHERE ABS(net_revenue - (quantity * unit_price - discount_amount)) > 0.01"
            ),
            description="net_revenue ~= quantity*unit_price - discount_amount (1-cent tolerance)",
            meta={
                "dimension": "Accuracy",
                "rationale": "Revenue arithmetic invariant with 1-cent tolerance for float rounding",
            },
        )
    )

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT sales_key, quantity, unit_cost, net_revenue, gross_profit "
                "FROM {batch} "
                "WHERE ABS(gross_profit - (net_revenue - (quantity * unit_cost))) > 0.01"
            ),
            description="gross_profit ~= net_revenue - (quantity*unit_cost) (1-cent tolerance)",
            meta={
                "dimension": "Accuracy",
                "rationale": "Profit arithmetic invariant with 1-cent tolerance for float rounding",
            },
        )
    )

    # ------------------------------------------------------------
    # 24 — Validity: order_id format/length sanity
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="order_id",
            min_value=5,
            max_value=20,
            meta={"dimension": "Validity",
                  "rationale": "order_id length sanity; D7 uses 'ORD-ORPHAN-####' (16 chars), fits range"},
        )
    )

    # ------------------------------------------------------------
    # 25 — Validity: order_line_num range
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="order_line_num",
            min_value=1,
            max_value=100,
            meta={"dimension": "Validity",
                  "rationale": "Order line numbers should be 1..N where N is reasonable ceiling"},
        )
    )

    return suite