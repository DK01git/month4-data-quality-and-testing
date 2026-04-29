"""
Month 4 — Expectation Suite: dim_product

Target: retaildw_dq.warehouse.dim_product
Rows:   ~1,000

Defects injected in this table (predicted FAIL expectations in parens):
    D5  Validity   15 rows list_price = 0           (#10)
    D6  Accuracy   10 rows cost_price > list_price  (#16)
                   + 15 cascade rows from D5 zeroing list_price
                   = 25 rows total expected to FAIL

Coverage:
    Completeness: 5 expectations
    Uniqueness:   2 expectations
    Validity:    14 expectations
    Accuracy:     1 expectation

Total: 22 expectations (predicted ~20 PASS / ~2 FAIL).

Author: Diluksha Perera
"""

from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe


SUITE_NAME = "dim_product_suite"


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # ------------------------------------------------------------
    # 1 & 2 — Whole-table invariants
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(
            min_value=800, max_value=1200,
            meta={"dimension": "Validity",
                  "rationale": "Expected ~1,000 products; buffer for catalog growth"},
        )
    )
    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchOrderedList(
            column_list=[
                "product_key", "product_id", "product_name", "category",
                "subcategory", "brand", "list_price", "cost_price", "is_active",
            ],
            meta={"dimension": "Validity",
                  "rationale": "Schema drift guard; 9 columns in declared order"},
        )
    )

    # ------------------------------------------------------------
    # 3-7 — Completeness
    # ------------------------------------------------------------

    for col, rationale in [
        ("product_key", "Surrogate PK — structurally required"),
        ("product_id", "Business natural key — required"),
        ("product_name", "Product name required for any downstream report"),
        ("is_active", "is_active flag required for filtering active catalog"),
        ("list_price", "list_price required for any pricing analytics"),
    ]:
        suite.add_expectation(
            gxe.ExpectColumnValuesToNotBeNull(
                column=col,
                meta={"dimension": "Completeness", "rationale": rationale},
            )
        )

    # ------------------------------------------------------------
    # 8 & 9 — Uniqueness
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="product_key",
            meta={"dimension": "Uniqueness",
                  "rationale": "product_key is the surrogate PK"},
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="product_id",
            meta={"dimension": "Uniqueness",
                  "rationale": "product_id is the business natural key — one row per product"},
        )
    )

    # ------------------------------------------------------------
    # 10 — Validity: list_price must be > 0
    # ------------------------------------------------------------
    # D5 sets list_price=0 on 15 rows — this expectation FAILS to catch them.

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="list_price", min_value=0.01, max_value=10000,
            meta={"dimension": "Validity",
                  "rationale": "list_price must be positive; upper bound catches encoding bugs",
                  "predicted": "FAIL — D5 injection (15 rows with list_price=0)"},
        )
    )

    # ------------------------------------------------------------
    # 11 — Validity: cost_price must be >= 0
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="cost_price", min_value=0, max_value=10000,
            meta={"dimension": "Validity",
                  "rationale": "cost_price must be non-negative"},
        )
    )

    # ------------------------------------------------------------
    # 12 — Validity: product_key range
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="product_key", min_value=1, max_value=100000,
            meta={"dimension": "Validity",
                  "rationale": "Surrogate keys positive and within sane range"},
        )
    )

    # ------------------------------------------------------------
    # 13 — Validity: is_active is boolean
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnDistinctValuesToBeInSet(
            column="is_active", value_set=[True, False],
            meta={"dimension": "Validity",
                  "rationale": "is_active should only take the two boolean values"},
        )
    )

    # ------------------------------------------------------------
    # 14 — Validity: product_id format
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT product_key, product_id "
                "FROM {batch} "
                "WHERE product_id !~ '^PRD[0-9]+$'"
            ),
            description="product_id must match format 'PRD' followed by digits",
            meta={"dimension": "Validity",
                  "rationale": "Business ID convention: 'PRD' prefix + numeric suffix"},
        )
    )

    # ------------------------------------------------------------
    # 15-17 — Validity: string length sanity
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="product_id", min_value=5, max_value=20,
            meta={"dimension": "Validity",
                  "rationale": "product_id format 'PRD#####' — 8 chars but allow range"},
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="product_name", min_value=3, max_value=100,
            meta={"dimension": "Validity",
                  "rationale": "Product names should be between 3 and 100 characters"},
        )
    )

    # ------------------------------------------------------------
    # 18 — Validity: category must be one of known values (relaxed)
    # ------------------------------------------------------------
    # Profile showed category 'Electronics' dominates; we don't assert
    # an exhaustive enum because the canonical list isn't formally
    # established. Length sanity is the next-best guard.

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="category", min_value=3, max_value=50, mostly=0.99,
            meta={"dimension": "Validity",
                  "rationale": "Category length sanity; accepts mostly=0.99 to handle any rare nulls"},
        )
    )

    # ------------------------------------------------------------
    # 19 — Validity: brand length sanity
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="brand", min_value=2, max_value=50, mostly=0.99,
            meta={"dimension": "Validity",
                  "rationale": "Brand length sanity; relaxed for null tolerance"},
        )
    )

    # ------------------------------------------------------------
    # 20 — Validity: subcategory length sanity
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="subcategory", min_value=3, max_value=50, mostly=0.99,
            meta={"dimension": "Validity",
                  "rationale": "Subcategory length sanity; relaxed for null tolerance"},
        )
    )

    # ------------------------------------------------------------
    # 21 — Validity: list_price reasonable upper bound
    # ------------------------------------------------------------
    # Profile showed max list_price of $499.75; we set ceiling at $1000
    # to catch encoding errors but allow for premium products.

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="list_price", min_value=0, max_value=1000, mostly=0.999,
            meta={"dimension": "Validity",
                  "rationale": "Per-profile ceiling; mostly=0.999 absorbs occasional premium products"},
        )
    )

    # ------------------------------------------------------------
    # 22 — Accuracy: cost_price <= list_price (cross-column invariant)
    # ------------------------------------------------------------
    # D6 sets cost_price = list_price + 50 on 10 rows.
    # Cascade: D5 zeroes list_price on 15 rows whose original cost_price > 0,
    # so cost_price > list_price holds for those too.
    # Total expected violations: 25.

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT product_key, product_id, list_price, cost_price "
                "FROM {batch} "
                "WHERE cost_price > list_price"
            ),
            description="cost_price must not exceed list_price (margin invariant)",
            meta={"dimension": "Accuracy",
                  "rationale": "Cross-column invariant: cost cannot exceed list price",
                  "predicted": "FAIL — D6 (10 rows) + cascade from D5 (15 rows) = 25 rows"},
        )
    )

    return suite
