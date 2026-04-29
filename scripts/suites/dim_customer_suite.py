"""
Month 4 — Expectation Suite: dim_customer

Target: retaildw_dq.warehouse.dim_customer
Rows:   ~10,010 (10,000 original + 10 duplicates from D2 injection)

Defects injected in this table (predicted FAIL expectations in parens):
    D1  Completeness  300 rows email = NULL        (#9)
    D2  Uniqueness    10 duplicate customer_ids    (#12, #27)
    D3  Validity      200 rows email = 'n/a'       (#13)
    D4  Validity      50 rows customer_segment typo (#14)

Coverage:
    Completeness: 8 expectations
    Uniqueness:   4 expectations
    Validity:    14 expectations
    Consistency:  2 expectations

Total: 28 expectations (predicted 24 PASS / 4 FAIL against retaildw_dq).

Author: Diluksha Perera
"""

from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe


SUITE_NAME = "dim_customer_suite"


# Valid enum sets — kept at module level for reuse in data contracts later
VALID_SEGMENTS = ["Standard", "Budget", "Premium"]
EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"


def build_suite() -> gx.ExpectationSuite:
    """
    Returns a fully populated ExpectationSuite for dim_customer.
    """
    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # ------------------------------------------------------------
    # 1 & 2 — Whole-table invariants
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(
            min_value=9000,
            max_value=11000,
            meta={
                "dimension": "Validity",
                "rationale": "Expected ~10,010 rows (10,000 original + 10 D2 dupes); wide tolerance for normal growth",
            },
        )
    )

    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchOrderedList(
            column_list=[
                "customer_key", "customer_id", "customer_name", "email",
                "city", "state", "zip_code", "customer_segment",
                "effective_date", "expiry_date", "is_current",
            ],
            meta={
                "dimension": "Validity",
                "rationale": "Schema drift guard; 11 columns must appear in declared order",
            },
        )
    )

    # ------------------------------------------------------------
    # 3-10 — Completeness (8 expectations)
    # ------------------------------------------------------------

    # Strict: these must never be null
    for col, rationale in [
        ("customer_key", "Surrogate PK — structurally required"),
        ("customer_id", "Business natural key — required"),
        ("customer_name", "Customer name required for any downstream report"),
        ("effective_date", "SCD2 record-start timestamp — required"),
        ("expiry_date", "SCD2 record-end timestamp — required (9999-12-31 sentinel OK)"),
        ("is_current", "SCD2 current-row flag — required"),
        ("customer_segment", "Segmentation required for customer analytics"),
    ]:
        suite.add_expectation(
            gxe.ExpectColumnValuesToNotBeNull(
                column=col,
                meta={"dimension": "Completeness", "rationale": rationale},
            )
        )

    # Relaxed: email has business-legitimate nulls (opt-out customers)
    # mostly=0.99 allows up to 1% null; D1 injects 3% nulls → this FAILS (intended)
    suite.add_expectation(
        gxe.ExpectColumnValuesToNotBeNull(
            column="email",
            mostly=0.99,
            meta={
                "dimension": "Completeness",
                "rationale": "Business allows ~1% email opt-out; injected D1 (3%) should exceed this",
                "predicted": "FAIL — D1 injection",
            },
        )
    )

    # ------------------------------------------------------------
    # 11 — Uniqueness: surrogate key
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="customer_key",
            meta={
                "dimension": "Uniqueness",
                "rationale": "customer_key is the surrogate PK; must be unique even in SCD2",
            },
        )
    )

    # ------------------------------------------------------------
    # 12 — Uniqueness: SCD2 current-row integrity via SQL
    # ------------------------------------------------------------
    # Business rule: only one is_current=TRUE row per customer_id.
    # GX's ExpectCompoundColumnsToBeUnique checks ALL rows, not filtered —
    # so we use UnexpectedRowsExpectation with a SQL filter.

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT customer_id, COUNT(*) AS current_row_count "
                "FROM {batch} "
                "WHERE is_current = TRUE "
                "GROUP BY customer_id "
                "HAVING COUNT(*) > 1"
            ),
            description="SCD2 integrity: at most one is_current=TRUE row per customer_id",
            meta={
                "dimension": "Uniqueness",
                "rationale": "SCD2 compound rule: customer_id has exactly one current row",
                "predicted": "FAIL — D2 injection (10 duplicates)",
            },
        )
    )

    # ------------------------------------------------------------
    # 13 — Validity: email regex format
    # ------------------------------------------------------------
    # GX's MatchRegex treats NULL as non-matching by default.
    # We set mostly=0.99 — consistent with the Completeness threshold.
    # D1 (300 NULL) + D3 (200 'n/a') = 500 non-matching out of 10,010 = 5%
    # → fails 0.99 threshold, caught.

    suite.add_expectation(
        gxe.ExpectColumnValuesToMatchRegex(
            column="email",
            regex=EMAIL_REGEX,
            mostly=0.99,
            meta={
                "dimension": "Validity",
                "rationale": "Email must match standard RFC-like regex; D3 injects 'n/a' sentinels",
                "predicted": "FAIL — D1 nulls + D3 'n/a' combined exceed 1% tolerance",
            },
        )
    )

    # ------------------------------------------------------------
    # 14 — Validity: customer_segment enum
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="customer_segment",
            value_set=VALID_SEGMENTS,
            meta={
                "dimension": "Validity",
                "rationale": "customer_segment must be one of the approved enum values",
                "predicted": "FAIL — D4 injection ('Platnium' typo, 50 rows)",
            },
        )
    )

    # ------------------------------------------------------------
    # 15-17 — Validity: string length sanity
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="customer_id",
            min_value=5,
            max_value=15,
            meta={"dimension": "Validity",
                  "rationale": "customer_id format 'CUS######' — 9 chars but allow range"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="customer_name",
            min_value=3,
            max_value=50,
            meta={"dimension": "Validity",
                  "rationale": "Names should be between 3 and 50 characters"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="email",
            min_value=5,
            max_value=100,
            mostly=0.95,  # email can be NULL (D1) or 'n/a' (D3, length 3) — accept some fail
            meta={
                "dimension": "Validity",
                "rationale": "Email length sanity; relaxed mostly to avoid double-fail with #13",
            },
        )
    )

    # ------------------------------------------------------------
    # 18 — Validity: zip_code range
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="zip_code",
            min_value=10000,
            max_value=99999,
            meta={
                "dimension": "Validity",
                "rationale": "US 5-digit zip range; catches integer-encoding errors for leading-zero zips",
            },
        )
    )

    # ------------------------------------------------------------
    # 19 — Validity: state code is exactly 2 characters
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="state",
            min_value=2,
            max_value=2,
            meta={"dimension": "Validity",
                  "rationale": "US state codes are exactly 2 uppercase letters"},
        )
    )

    # ------------------------------------------------------------
    # 20 — Validity: effective_date range
    # ------------------------------------------------------------
    # D2 inserts use CURRENT_DATE, which is 2026-04-XX — well within range.

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="effective_date",
            min_value="2020-01-01",
            max_value="2030-12-31",
            meta={
                "dimension": "Validity",
                "rationale": "Customer records shouldn't have effective dates outside the warehouse's time horizon",
            },
        )
    )

    # ------------------------------------------------------------
    # 21 — Consistency: expiry_date >= effective_date
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT customer_key, customer_id, effective_date, expiry_date "
                "FROM {batch} "
                "WHERE expiry_date < effective_date"
            ),
            description="SCD2 integrity: expiry_date must be >= effective_date",
            meta={"dimension": "Consistency",
                  "rationale": "Temporal invariant: a record cannot expire before it became effective"},
        )
    )

    # ------------------------------------------------------------
    # 22 — Consistency: current rows must have expiry_date = 9999-12-31
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT customer_key, customer_id, effective_date, expiry_date "
                "FROM {batch} "
                "WHERE is_current = TRUE AND expiry_date <> DATE '9999-12-31'"
            ),
            description="SCD2 convention: is_current=TRUE rows carry expiry_date = 9999-12-31",
            meta={
                "dimension": "Consistency",
                "rationale": "Industry-standard SCD2 sentinel for open-ended current records",
            },
        )
    )

    # ------------------------------------------------------------
    # 23 — Validity: is_current is a boolean
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnDistinctValuesToBeInSet(
            column="is_current",
            value_set=[True, False],
            meta={"dimension": "Validity",
                  "rationale": "is_current should only take the two boolean values"},
        )
    )

    # ------------------------------------------------------------
    # 24 — Validity: customer_key surrogate range
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="customer_key",
            min_value=1,
            max_value=200000,
            meta={"dimension": "Validity",
                  "rationale": "Surrogate keys should be positive and within sane range (D2 inserts use +100000 offset)"},
        )
    )

    # ------------------------------------------------------------
    # 25 — Validity: customer_segment length bound
    # ------------------------------------------------------------
    # Note: 'Platnium' (D4 typo) is 8 characters — within this range.
    # This expectation PASSES; the typo is caught by #14 (enum check), not here.

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="customer_segment",
            min_value=5,
            max_value=20,
            meta={
                "dimension": "Validity",
                "rationale": "Length sanity for segment values (typo still passes length, caught by enum #14)",
            },
        )
    )

    # ------------------------------------------------------------
    # 26 — Validity: customer_id format
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT customer_key, customer_id "
                "FROM {batch} "
                "WHERE customer_id !~ '^CUS[0-9]+$'"
            ),
            description="customer_id must match format 'CUS' followed by digits",
            meta={"dimension": "Validity",
                  "rationale": "Business ID convention: 'CUS' prefix + numeric suffix"},
        )
    )

    # ------------------------------------------------------------
    # 27 — Uniqueness (distribution): customer_id distinct-ratio
    # ------------------------------------------------------------
    # Math: 10,000 distinct / 10,010 rows = 0.999001 after D2 injection.
    # Clean baseline: 1.000.
    # Threshold 0.9995 → FAILs at 0.999, catching D2.

    suite.add_expectation(
        gxe.ExpectColumnProportionOfUniqueValuesToBeBetween(
            column="customer_id",
            min_value=0.9995,
            max_value=1.0,
            meta={
                "dimension": "Uniqueness",
                "rationale": "SCD2 may have some history, but customer_id ratio should stay near 1.0",
                "predicted": "FAIL — D2 injection drops ratio to ~0.999",
            },
        )
    )

    # ------------------------------------------------------------
    # 28 — Uniqueness: no duplicate customer_key (redundant with #11 via SQL)
    # ------------------------------------------------------------
    # This is a SQL-based cross-check that will PASS because D2
    # preserved key uniqueness (+100000 offset).

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT customer_key, COUNT(*) AS dup_count "
                "FROM {batch} "
                "GROUP BY customer_key "
                "HAVING COUNT(*) > 1"
            ),
            description="customer_key must be unique (surrogate PK invariant via SQL)",
            meta={"dimension": "Uniqueness",
                  "rationale": "Independent SQL verification of surrogate PK uniqueness"},
        )
    )

    return suite