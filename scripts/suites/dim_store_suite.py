"""
Month 4 — Expectation Suite: dim_store

Target: retaildw_dq.warehouse.dim_store
Rows:   ~200 (no defects injected)

Coverage:
    Completeness: 5 expectations
    Uniqueness:   2 expectations
    Validity:    13 expectations

Total: 20 expectations (predicted 20/20 PASS).

Author: Diluksha Perera
"""

from __future__ import annotations

import great_expectations as gx
from great_expectations import expectations as gxe


SUITE_NAME = "dim_store_suite"

VALID_STORE_TYPES = ["Standard", "Express", "Flagship"]
VALID_REGIONS = ["West", "South", "Northeast", "Midwest"]


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # ------------------------------------------------------------
    # 1 & 2 — Whole-table invariants
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(
            min_value=150, max_value=300,
            meta={"dimension": "Validity",
                  "rationale": "Expected ~200 stores; buffer for organic growth"},
        )
    )
    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchOrderedList(
            column_list=[
                "store_key", "store_id", "store_name", "city", "state",
                "region", "store_type", "opening_date",
            ],
            meta={"dimension": "Validity",
                  "rationale": "Schema drift guard; 8 columns in declared order"},
        )
    )

    # ------------------------------------------------------------
    # 3-7 — Completeness
    # ------------------------------------------------------------

    for col, rationale in [
        ("store_key", "Surrogate PK — structurally required"),
        ("store_id", "Business natural key — required"),
        ("store_name", "Store name required for any downstream report"),
        ("opening_date", "Opening date required for store age analytics"),
        ("state", "State required for geographic analytics"),
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
            column="store_key",
            meta={"dimension": "Uniqueness",
                  "rationale": "store_key is the surrogate PK"},
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeUnique(
            column="store_id",
            meta={"dimension": "Uniqueness",
                  "rationale": "store_id is the business natural key — one row per store"},
        )
    )

    # ------------------------------------------------------------
    # 10 — Validity: store_key range
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="store_key", min_value=1, max_value=10000,
            meta={"dimension": "Validity",
                  "rationale": "Surrogate keys positive and within sane range"},
        )
    )

    # ------------------------------------------------------------
    # 11 & 12 — Validity: enumerated value sets
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="store_type", value_set=VALID_STORE_TYPES,
            meta={"dimension": "Validity",
                  "rationale": "store_type must be one of the canonical store formats"},
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="region", value_set=VALID_REGIONS,
            meta={"dimension": "Validity",
                  "rationale": "region must be one of the canonical US regions"},
        )
    )

    # ------------------------------------------------------------
    # 13 — Validity: state code length (must be exactly 2)
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="state", min_value=2, max_value=2,
            meta={"dimension": "Validity",
                  "rationale": "US state codes are exactly 2 uppercase letters"},
        )
    )

    # ------------------------------------------------------------
    # 14 — Validity: store_id format
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT store_key, store_id "
                "FROM {batch} "
                "WHERE store_id !~ '^STR[0-9]+$'"
            ),
            description="store_id must match format 'STR' followed by digits",
            meta={"dimension": "Validity",
                  "rationale": "Business ID convention: 'STR' prefix + numeric suffix"},
        )
    )

    # ------------------------------------------------------------
    # 15-17 — Validity: string length sanity
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="store_id", min_value=5, max_value=15,
            meta={"dimension": "Validity",
                  "rationale": "store_id format 'STR####' — typical 7 chars; allow range"},
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="store_name", min_value=3, max_value=100,
            meta={"dimension": "Validity",
                  "rationale": "Store names should be between 3 and 100 characters"},
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="city", min_value=2, max_value=50,
            meta={"dimension": "Validity",
                  "rationale": "City names between 2 and 50 characters"},
        )
    )

    # ------------------------------------------------------------
    # 18 — Validity: opening_date must not be in the future
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT store_key, store_id, opening_date "
                "FROM {batch} "
                "WHERE opening_date > CURRENT_DATE"
            ),
            description="opening_date must be on or before today",
            meta={"dimension": "Validity",
                  "rationale": "A store cannot have opened in the future"},
        )
    )

    # ------------------------------------------------------------
    # 19 — Validity: opening_date business range
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="opening_date",
            min_value="1990-01-01", max_value="2030-12-31",
            meta={"dimension": "Validity",
                  "rationale": "Store opening dates should fall within business horizon (1990-2030)"},
        )
    )

    # ------------------------------------------------------------
    # 20 — Validity: store_type distribution sanity (no single type dominates >70%)
    # ------------------------------------------------------------

    suite.add_expectation(
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=(
                "SELECT store_type, store_count, ratio "
                "FROM ("
                "  SELECT store_type, "
                "         COUNT(*) AS store_count, "
                "         CAST(COUNT(*) AS FLOAT) / NULLIF(SUM(COUNT(*)) OVER (), 0) AS ratio "
                "  FROM {batch} "
                "  GROUP BY store_type"
                ") t "
                "WHERE ratio > 0.70"
            ),
            description="No single store_type should account for more than 70% of all stores",
            meta={"dimension": "Validity",
                  "rationale": "Distribution sanity: a healthy retailer has portfolio diversity"},
        )
    )

    return suite
