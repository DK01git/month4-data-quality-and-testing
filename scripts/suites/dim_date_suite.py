"""
Month 4 — Expectation Suite: dim_date

Tables: retaildw_dq.warehouse.dim_date
Rows expected: ~366 (one per day of 2024)
Defects injected into this table: NONE — expected 100% PASS.

Coverage:
    Completeness: 5 expectations
    Uniqueness:   2 expectations
    Validity:    12 expectations
    Consistency:  1 expectation

Author: Diluksha Perera
"""

from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe


SUITE_NAME = "dim_date_suite"


def build_suite() -> gx.ExpectationSuite:
    """
    Returns a fully populated ExpectationSuite for dim_date.

    Not attached to a context here; the caller is responsible for
    registering this suite with a DataContext via context.suites.add().
    """
    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # ------------------------------------------------------------
    # 1 & 2 — Whole-table invariants
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(
            min_value=300,
            max_value=400,
            meta={"dimension": "Validity",
                  "rationale": "One row per day for ~1 year; leap/non-leap tolerance"},
        )
    )

    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchOrderedList(
            column_list=[
                "date_key", "full_date", "year_number", "quarter_number",
                "month_number", "month_name", "day_of_week", "day_name",
                "is_weekend", "is_holiday",
            ],
            meta={"dimension": "Validity",
                  "rationale": "Schema drift guard; columns must appear in fixed order"},
        )
    )

    # ------------------------------------------------------------
    # 3-7 — Completeness: critical columns must not be NULL
    # ------------------------------------------------------------

    for col in ("date_key", "full_date", "year_number", "month_number", "quarter_number"):
        suite.add_expectation(
            gxe.ExpectColumnValuesToNotBeNull(
                column=col,
                meta={"dimension": "Completeness",
                      "rationale": f"{col} is structurally required"},
            )
        )

    # ------------------------------------------------------------
    # 8 & 9 — Uniqueness: date dimension must have one row per date
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="date_key",
            meta={"dimension": "Uniqueness",
                  "rationale": "date_key is the surrogate PK"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="full_date",
            meta={"dimension": "Uniqueness",
                  "rationale": "One calendar date should appear exactly once"},
        )
    )

    # ------------------------------------------------------------
    # 10-14 — Validity: numeric ranges
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="date_key",
            min_value=19000101,
            max_value=21001231,
            meta={"dimension": "Validity",
                  "rationale": "date_key format YYYYMMDD; ~1900-2100 is the valid universe"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="month_number",
            min_value=1,
            max_value=12,
            meta={"dimension": "Validity",
                  "rationale": "Calendar constraint: months are 1..12"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="quarter_number",
            min_value=1,
            max_value=4,
            meta={"dimension": "Validity",
                  "rationale": "Calendar constraint: quarters are 1..4"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="day_of_week",
            min_value=1,
            max_value=7,
            meta={"dimension": "Validity",
                  "rationale": "Calendar constraint: day_of_week is 1..7"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="year_number",
            min_value=2020,
            max_value=2030,
            meta={"dimension": "Validity",
                  "rationale": "Business-reasonable year range for the warehouse"},
        )
    )

    # ------------------------------------------------------------
    # 15 & 16 — Validity: enumerated sets
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="month_name",
            value_set=[
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ],
            meta={"dimension": "Validity",
                  "rationale": "month_name must be one of 12 canonical English month names"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="day_name",
            value_set=[
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            ],
            meta={"dimension": "Validity",
                  "rationale": "day_name must be one of 7 canonical English day names"},
        )
    )

    # ------------------------------------------------------------
    # 17 & 18 — Validity: string length bounds
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="month_name",
            min_value=3,
            max_value=9,
            meta={"dimension": "Validity",
                  "rationale": "Shortest 'May' (3), longest 'September' (9)"},
        )
    )

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="day_name",
            min_value=6,
            max_value=9,
            meta={"dimension": "Validity",
                  "rationale": "Shortest 'Monday'/'Friday' (6), longest 'Wednesday' (9)"},
        )
    )

    # ------------------------------------------------------------
    # 19 — Consistency: year_number must match EXTRACT(YEAR FROM full_date)
    # ------------------------------------------------------------
    # Uses UnexpectedRowsExpectation — the GX idiom for SQL-expressed
    # cross-column rules that go beyond the built-in pair comparisons.

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT date_key, full_date, year_number "
                "FROM {batch} "
                "WHERE year_number <> EXTRACT(YEAR FROM full_date)::INT"
            ),
            description="year_number must equal EXTRACT(YEAR FROM full_date)",
            meta={"dimension": "Consistency",
                  "rationale": "Cross-column invariant: stored year must match date's year"},
        )
    )

    # ------------------------------------------------------------
    # 20 — Validity (volumetric): is_weekend should be ~28.6% of rows
    # ------------------------------------------------------------
    # Weekend = Sat + Sun = 2/7 ≈ 28.6%. Tolerance 25-32%.
    # Implemented as SQL because GX's built-in proportion checks
    # don't express "proportion of rows with a boolean = TRUE".

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT 1 AS anomaly "
                "FROM (SELECT "
                "       CAST(COUNT(*) FILTER (WHERE is_weekend = TRUE) AS FLOAT) "
                "       / NULLIF(COUNT(*), 0) AS weekend_ratio "
                "      FROM {batch}) r "
                "WHERE r.weekend_ratio NOT BETWEEN 0.25 AND 0.32"
            ),
            description="is_weekend proportion must be within 25%-32% (~2/7 of days)",
            meta={"dimension": "Validity",
                  "rationale": "Volumetric sanity: weekends are ~28.6% of a calendar year"},
        )
    )

    return suite