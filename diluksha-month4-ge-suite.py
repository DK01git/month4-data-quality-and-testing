"""
Month 4 Deliverable — Great Expectations Suite (Consolidated)
=============================================================
RetailCo Retail Data Warehouse — Data Quality Framework
Author  : Diluksha Perera
Date    : 2026-04-29
Target  : retaildw_dq.warehouse (PostgreSQL mirror with injected defects)

Tables covered (expectations per table):
    dim_customer  — 28 expectations
    dim_product   — 21 expectations
    dim_store     — 20 expectations
    dim_date      — 20 expectations
    fact_sales    — 25 expectations
    ─────────────────────────────────
    TOTAL         — 114 expectations

Injected defects and predicted outcomes:
    D1  dim_customer  300 rows  email = NULL           → FAIL  DQ-001
    D2  dim_customer  10  rows  duplicate is_current   → FAIL  DQ-002
    D3  dim_customer  200 rows  email = 'n/a'          → FAIL  DQ-003
    D4  dim_customer  50  rows  segment typo 'Platnium'→ FAIL  DQ-004
    D5  dim_product   15  rows  list_price = 0         → FAIL  DQ-005
    D6  dim_product   10  rows  cost_price > list_price→ FAIL  DQ-006
    D7  fact_sales    50  rows  orphan customer_key    → FAIL  DQ-007
    D8  fact_sales    100 rows  quantity = -1          → FAIL  DQ-008

Usage:
    cd C:\\de-training\\month4
    python diluksha-month4-ge-suite.py

    # Optionally run a single table:
    python diluksha-month4-ge-suite.py --table dim_customer
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import great_expectations as gx
from great_expectations import expectations as gxe

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
GX_DIR = PROJECT_ROOT / "gx"

DATASOURCE_NAME = "retail_warehouse_dq"
DB_CONN = "postgresql+psycopg2://dataeng:dataeng123@localhost:5432/retaildw_dq"

# ---------------------------------------------------------------------------
# Shared constants (also referenced by data contracts)
# ---------------------------------------------------------------------------
VALID_SEGMENTS       = ["Standard", "Budget", "Premium"]
VALID_STORE_TYPES    = ["Standard", "Express", "Flagship"]
VALID_REGIONS        = ["West", "South", "Northeast", "Midwest"]
VALID_DAY_NAMES      = ["Monday", "Tuesday", "Wednesday", "Thursday",
                        "Friday", "Saturday", "Sunday"]
VALID_MONTH_NAMES    = ["January", "February", "March", "April", "May",
                        "June", "July", "August", "September", "October",
                        "November", "December"]
EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"


# ===========================================================================
# SUITE BUILDERS
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. dim_customer  (28 expectations)
# ---------------------------------------------------------------------------
def build_dim_customer_suite() -> gx.ExpectationSuite:
    """
    Covers Completeness (8), Uniqueness (4), Validity (14), Consistency (2).
    Predicted FAIL: DQ-001 (#9), DQ-002 (#12, #27), DQ-003 (#13), DQ-004 (#14).
    """
    suite = gx.ExpectationSuite(name="dim_customer_suite")

    # ── Whole-table invariants ──────────────────────────────────────────────
    # #1 Row count
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(
        min_value=9_000, max_value=11_000,
        meta={"dimension": "Validity",
              "rationale": "~10,010 rows (10k base + 10 D2 dupes); wide buffer for growth"},
    ))
    # #2 Schema drift guard
    suite.add_expectation(gxe.ExpectTableColumnsToMatchOrderedList(
        column_list=["customer_key", "customer_id", "customer_name", "email",
                     "city", "state", "zip_code", "customer_segment",
                     "effective_date", "expiry_date", "is_current"],
        meta={"dimension": "Validity",
              "rationale": "11 columns in declared order; catches upstream schema changes"},
    ))

    # ── Completeness (8 expectations) ──────────────────────────────────────
    # #3-9 — strict NOT NULL for required fields
    for col, rationale in [
        ("customer_key",     "Surrogate PK — structurally required"),
        ("customer_id",      "Business natural key — required"),
        ("customer_name",    "Customer name required for all downstream reports"),
        ("effective_date",   "SCD2 record-start timestamp — required"),
        ("expiry_date",      "SCD2 record-end timestamp — required (9999-12-31 sentinel OK)"),
        ("is_current",       "SCD2 current-row flag — required"),
        ("customer_segment", "Segmentation required for customer analytics"),
    ]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
            column=col,
            meta={"dimension": "Completeness", "rationale": rationale},
        ))
    # #9 — email: mostly=0.99 (1% opt-out budget); D1 injects 3% → FAIL (DQ-001)
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="email", mostly=0.99,
        meta={"dimension": "Completeness",
              "rationale": "Business allows ~1% email opt-out; D1 injects 3% NULLs",
              "issue_id": "DQ-001", "predicted": "FAIL"},
    ))

    # ── Uniqueness (4 expectations) ─────────────────────────────────────────
    # #10 surrogate PK unique
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="customer_key",
        meta={"dimension": "Uniqueness",
              "rationale": "customer_key is surrogate PK; must be unique across all SCD2 rows"},
    ))
    # #11 compound SCD2: (customer_id + effective_date) grain
    suite.add_expectation(gxe.ExpectCompoundColumnsToBeUnique(
        column_list=["customer_id", "effective_date"],
        meta={"dimension": "Uniqueness",
              "rationale": "SCD2 grain: a customer cannot have two records with same start date"},
    ))
    # #12 SQL: at most one is_current=TRUE per customer_id (DQ-002)
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT customer_id, COUNT(*) AS current_row_count "
            "FROM {batch} "
            "WHERE is_current = TRUE "
            "GROUP BY customer_id "
            "HAVING COUNT(*) > 1"
        ),
        description="SCD2 integrity: exactly one is_current=TRUE row per customer_id",
        meta={"dimension": "Uniqueness",
              "rationale": "D2 injects 10 duplicate current rows",
              "issue_id": "DQ-002", "predicted": "FAIL"},
    ))
    # #27 proportion of unique customer_ids (statistical uniqueness)
    suite.add_expectation(gxe.ExpectColumnProportionOfUniqueValuesToBeBetween(
        column="customer_id", min_value=0.9995, max_value=1.0,
        meta={"dimension": "Uniqueness",
              "rationale": "D2 drops ratio to ~0.999 (10 dupes / 10,010 rows)",
              "issue_id": "DQ-002", "predicted": "FAIL"},
    ))
    # #28 SQL: no duplicate customer_key (independent verification)
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT customer_key, COUNT(*) AS dup_count "
            "FROM {batch} "
            "GROUP BY customer_key "
            "HAVING COUNT(*) > 1"
        ),
        description="customer_key must be unique (SQL cross-check)",
        meta={"dimension": "Uniqueness",
              "rationale": "D2 uses +100000 offset so customer_key stays unique — expects PASS"},
    ))

    # ── Validity (14 expectations) ──────────────────────────────────────────
    # #13 email regex — D1 (300 NULLs) + D3 (200 'n/a') = ~5% non-matching → FAIL (DQ-003)
    suite.add_expectation(gxe.ExpectColumnValuesToMatchRegex(
        column="email", regex=EMAIL_REGEX, mostly=0.99,
        meta={"dimension": "Validity",
              "rationale": "D1 nulls + D3 'n/a' sentinels combined exceed 1% tolerance",
              "issue_id": "DQ-003", "predicted": "FAIL"},
    ))
    # #14 segment enum — D4 injects 'Platnium' typo → FAIL (DQ-004)
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(
        column="customer_segment", value_set=VALID_SEGMENTS,
        meta={"dimension": "Validity",
              "rationale": "D4 injects 'Platnium' (50 rows); not in approved enum",
              "issue_id": "DQ-004", "predicted": "FAIL"},
    ))
    # #15 customer_id format CUS + digits
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT customer_key, customer_id "
            "FROM {batch} "
            "WHERE customer_id !~ '^CUS[0-9]+$'"
        ),
        description="customer_id must match pattern CUS[digits]",
        meta={"dimension": "Validity",
              "rationale": "Business ID convention enforced by source CRM"},
    ))
    # #16 customer_id length
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="customer_id", min_value=5, max_value=15,
        meta={"dimension": "Validity", "rationale": "CUS###### format = 9 chars; allow range"},
    ))
    # #17 customer_name length
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="customer_name", min_value=3, max_value=50,
        meta={"dimension": "Validity", "rationale": "Name length sanity"},
    ))
    # #18 email length
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="email", min_value=5, max_value=100, mostly=0.95,
        meta={"dimension": "Validity",
              "rationale": "Email length sanity; relaxed mostly to avoid duplicate fail with #13"},
    ))
    # #19 zip_code range (US 5-digit)
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="zip_code", min_value=10_000, max_value=99_999,
        meta={"dimension": "Validity", "rationale": "US 5-digit zip integer range"},
    ))
    # #20 state code length = 2
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="state", min_value=2, max_value=2,
        meta={"dimension": "Validity", "rationale": "US state codes are exactly 2 uppercase letters"},
    ))
    # #21 effective_date range
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="effective_date", min_value="2020-01-01", max_value="2030-12-31",
        meta={"dimension": "Validity", "rationale": "Warehouse time horizon 2020-2030"},
    ))
    # #22 customer_key surrogate range
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="customer_key", min_value=1, max_value=200_000,
        meta={"dimension": "Validity",
              "rationale": "Surrogate keys positive; D2 uses +100000 offset, still in range"},
    ))
    # #23 customer_segment length sanity (typo 'Platnium' is 8 chars, passes length, caught by #14)
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="customer_segment", min_value=5, max_value=20,
        meta={"dimension": "Validity", "rationale": "Length sanity; typo caught by enum check #14"},
    ))
    # #24 is_current boolean
    suite.add_expectation(gxe.ExpectColumnDistinctValuesToBeInSet(
        column="is_current", value_set=[True, False],
        meta={"dimension": "Validity", "rationale": "is_current is boolean — only TRUE/FALSE"},
    ))
    # #25 expiry_date range
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="expiry_date", min_value="2020-01-01", max_value="9999-12-31",
        meta={"dimension": "Validity",
              "rationale": "Expiry includes 9999-12-31 sentinel for current rows"},
    ))
    # #26 city length sanity
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="city", min_value=2, max_value=50,
        meta={"dimension": "Validity", "rationale": "City name length sanity"},
    ))

    # ── Consistency (2 expectations) ────────────────────────────────────────
    # #29 expiry_date >= effective_date
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT customer_key, effective_date, expiry_date "
            "FROM {batch} "
            "WHERE expiry_date < effective_date"
        ),
        description="SCD2 temporal: expiry_date must be >= effective_date",
        meta={"dimension": "Consistency",
              "rationale": "A record cannot expire before it became effective"},
    ))
    # #30 current rows must carry sentinel expiry_date
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT customer_key, expiry_date "
            "FROM {batch} "
            "WHERE is_current = TRUE AND expiry_date <> DATE '9999-12-31'"
        ),
        description="Current SCD2 rows must carry expiry_date = 9999-12-31",
        meta={"dimension": "Consistency",
              "rationale": "Industry-standard SCD2 open-ended sentinel convention"},
    ))

    return suite


# ---------------------------------------------------------------------------
# 2. dim_product  (21 expectations)
# ---------------------------------------------------------------------------
def build_dim_product_suite() -> gx.ExpectationSuite:
    """
    Covers Completeness (5), Uniqueness (2), Validity (13), Accuracy (1).
    Predicted FAIL: DQ-005 (#10), DQ-006 (#21).
    """
    suite = gx.ExpectationSuite(name="dim_product_suite")

    # #1 Row count
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(
        min_value=800, max_value=1_200,
        meta={"dimension": "Validity", "rationale": "~1,000 products; buffer for catalog growth"},
    ))
    # #2 Schema drift guard
    suite.add_expectation(gxe.ExpectTableColumnsToMatchOrderedList(
        column_list=["product_key", "product_id", "product_name", "category",
                     "subcategory", "brand", "list_price", "cost_price", "is_active"],
        meta={"dimension": "Validity", "rationale": "9 columns in declared order"},
    ))

    # ── Completeness (5) ────────────────────────────────────────────────────
    for col, rationale in [
        ("product_key",  "Surrogate PK — structurally required"),
        ("product_id",   "Business natural key — required"),
        ("product_name", "Product name required for downstream reports"),
        ("is_active",    "is_active flag required for active catalog filtering"),
        ("list_price",   "list_price required for pricing analytics"),
    ]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
            column=col,
            meta={"dimension": "Completeness", "rationale": rationale},
        ))

    # ── Uniqueness (2) ──────────────────────────────────────────────────────
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="product_key",
        meta={"dimension": "Uniqueness", "rationale": "Surrogate PK must be globally unique"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="product_id",
        meta={"dimension": "Uniqueness", "rationale": "Business natural key must be unique"},
    ))

    # ── Validity (13) ───────────────────────────────────────────────────────
    # #10 list_price > 0 — D5 injects 15 rows with list_price=0 → FAIL (DQ-005)
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="list_price", min_value=0.01, max_value=100_000,
        meta={"dimension": "Validity",
              "rationale": "D5 injects list_price=0 on 15 products",
              "issue_id": "DQ-005", "predicted": "FAIL"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="cost_price", min_value=0, max_value=100_000,
        meta={"dimension": "Validity", "rationale": "cost_price >= 0; zero allowed for promotional items"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="product_key", min_value=1, max_value=50_000,
        meta={"dimension": "Validity", "rationale": "Surrogate key range sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="product_id", min_value=4, max_value=20,
        meta={"dimension": "Validity", "rationale": "Product ID length sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="product_name", min_value=3, max_value=100,
        meta={"dimension": "Validity", "rationale": "Product name length sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnDistinctValuesToBeInSet(
        column="is_active", value_set=[True, False],
        meta={"dimension": "Validity", "rationale": "is_active is boolean"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="category",
        meta={"dimension": "Validity", "rationale": "Category required for product hierarchy"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="category", min_value=2, max_value=50,
        meta={"dimension": "Validity", "rationale": "Category length sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="brand",
        meta={"dimension": "Validity", "rationale": "Brand required for brand-level analytics"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="brand", min_value=2, max_value=50,
        meta={"dimension": "Validity", "rationale": "Brand name length sanity"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT product_key, product_id "
            "FROM {batch} "
            "WHERE product_id !~ '^PROD[0-9]+$'"
        ),
        description="product_id must match PROD[digits] format",
        meta={"dimension": "Validity", "rationale": "Business ID convention"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="subcategory",
        meta={"dimension": "Validity", "rationale": "Subcategory required for drill-down analytics"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="subcategory", min_value=2, max_value=50,
        meta={"dimension": "Validity", "rationale": "Subcategory length sanity"},
    ))

    # ── Accuracy (1) ────────────────────────────────────────────────────────
    # #21 cost_price < list_price — D6 injects 10 rows where cost > list → FAIL (DQ-006)
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT product_key, product_id, list_price, cost_price "
            "FROM {batch} "
            "WHERE cost_price >= list_price AND list_price > 0"
        ),
        description="cost_price must be strictly less than list_price (positive margin required)",
        meta={"dimension": "Accuracy",
              "rationale": "D6 injects 10 rows where cost > list; zero-price rows excluded",
              "issue_id": "DQ-006", "predicted": "FAIL"},
    ))

    return suite


# ---------------------------------------------------------------------------
# 3. dim_store  (20 expectations)
# ---------------------------------------------------------------------------
def build_dim_store_suite() -> gx.ExpectationSuite:
    """
    Covers Completeness (5), Uniqueness (2), Validity (13).
    No defects injected — all 20 expected to PASS.
    """
    suite = gx.ExpectationSuite(name="dim_store_suite")

    # #1 Row count
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(
        min_value=150, max_value=300,
        meta={"dimension": "Validity", "rationale": "~200 stores; buffer for organic growth"},
    ))
    # #2 Schema drift guard
    suite.add_expectation(gxe.ExpectTableColumnsToMatchOrderedList(
        column_list=["store_key", "store_id", "store_name", "city", "state",
                     "region", "store_type", "opening_date"],
        meta={"dimension": "Validity", "rationale": "8 columns in declared order"},
    ))

    # ── Completeness (5) ────────────────────────────────────────────────────
    for col, rationale in [
        ("store_key",    "Surrogate PK — structurally required"),
        ("store_id",     "Business natural key — required"),
        ("store_name",   "Store name required for all location reports"),
        ("opening_date", "Opening date required for store age analytics"),
        ("region",       "Region required for geographic rollups"),
    ]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
            column=col,
            meta={"dimension": "Completeness", "rationale": rationale},
        ))

    # ── Uniqueness (2) ──────────────────────────────────────────────────────
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="store_key",
        meta={"dimension": "Uniqueness", "rationale": "Surrogate PK must be globally unique"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="store_id",
        meta={"dimension": "Uniqueness", "rationale": "Business natural key must be unique"},
    ))

    # ── Validity (13) ───────────────────────────────────────────────────────
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(
        column="store_type", value_set=VALID_STORE_TYPES,
        meta={"dimension": "Validity", "rationale": "store_type must be in approved enum"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(
        column="region", value_set=VALID_REGIONS,
        meta={"dimension": "Validity", "rationale": "region must be one of the four US regions"},
    ))
    # opening_date: lower bound static (2000-01-01), upper bound DYNAMIC via SQL.
    # IMPORTANT: ExpectColumnValuesToBeBetween with a hardcoded year like "2026-12-31"
    # would silently PASS future dates within the same year (e.g., a store opening
    # 2026-11-01 when today is 2026-04-29).  The challenge brief flags exactly this
    # class of error ("5 stores with opening_date in the future").
    # Using UnexpectedRowsExpectation with CURRENT_DATE is the correct pattern.
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="opening_date", min_value="2000-01-01", max_value="2099-12-31",
        meta={"dimension": "Validity",
              "rationale": "Broad range guard; actual future-date check handled by SQL below"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT store_key, store_id, store_name, opening_date "
            "FROM {batch} "
            "WHERE opening_date > CURRENT_DATE"
        ),
        description="opening_date must not be in the future (dynamic CURRENT_DATE check)",
        meta={"dimension": "Validity",
              "rationale": "Dynamic guard: catches any future date regardless of calendar year. "
                           "Challenge brief DQ scenario: 5 stores with opening_date in the future."},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="store_key", min_value=1, max_value=10_000,
        meta={"dimension": "Validity", "rationale": "Surrogate key range sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="store_id", min_value=4, max_value=15,
        meta={"dimension": "Validity", "rationale": "Store ID length sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="store_name", min_value=3, max_value=80,
        meta={"dimension": "Validity", "rationale": "Store name length sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="city", min_value=2, max_value=50,
        meta={"dimension": "Validity", "rationale": "City name length sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="state", min_value=2, max_value=2,
        meta={"dimension": "Validity", "rationale": "US state code is exactly 2 chars"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT store_key, store_id "
            "FROM {batch} "
            "WHERE store_id !~ '^STR[0-9]+$'"
        ),
        description="store_id must match STR[digits] format",
        meta={"dimension": "Validity", "rationale": "Business ID convention"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="city",
        meta={"dimension": "Validity", "rationale": "City required for location analytics"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="state",
        meta={"dimension": "Validity", "rationale": "State required for geographic rollups"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="store_type",
        meta={"dimension": "Validity", "rationale": "store_type required for channel analytics"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="region", min_value=4, max_value=20,
        meta={"dimension": "Validity", "rationale": "Region name length sanity"},
    ))

    return suite


# ---------------------------------------------------------------------------
# 4. dim_date  (20 expectations)
# ---------------------------------------------------------------------------
def build_dim_date_suite() -> gx.ExpectationSuite:
    """
    Covers Completeness (5), Uniqueness (2), Validity (12), Consistency (1).
    No defects injected — all 20 expected to PASS.
    """
    suite = gx.ExpectationSuite(name="dim_date_suite")

    # #1 Row count (~366 for a leap year calendar)
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(
        min_value=300, max_value=400,
        meta={"dimension": "Validity", "rationale": "One row per calendar day; leap/non-leap tolerance"},
    ))
    # #2 Schema drift guard
    suite.add_expectation(gxe.ExpectTableColumnsToMatchOrderedList(
        column_list=["date_key", "full_date", "year_number", "quarter_number",
                     "month_number", "month_name", "day_of_week", "day_name",
                     "is_weekend", "is_holiday"],
        meta={"dimension": "Validity", "rationale": "10 columns in declared order"},
    ))

    # ── Completeness (5) ────────────────────────────────────────────────────
    for col, rationale in [
        ("date_key",   "Surrogate PK — integer YYYYMMDD key"),
        ("full_date",  "Calendar date — required for all temporal joins"),
        ("month_name", "Month name required for reporting labels"),
        ("day_name",   "Day name required for weekly pattern analysis"),
        ("is_weekend", "Weekend flag required for traffic pattern analysis"),
    ]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
            column=col,
            meta={"dimension": "Completeness", "rationale": rationale},
        ))

    # ── Uniqueness (2) ──────────────────────────────────────────────────────
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="date_key",
        meta={"dimension": "Uniqueness", "rationale": "date_key is the PK; one row per day"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="full_date",
        meta={"dimension": "Uniqueness", "rationale": "full_date must also be unique (alternate key)"},
    ))

    # ── Validity (12) ───────────────────────────────────────────────────────
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="year_number", min_value=2020, max_value=2030,
        meta={"dimension": "Validity", "rationale": "Warehouse covers 2020-2030"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="quarter_number", min_value=1, max_value=4,
        meta={"dimension": "Validity", "rationale": "Quarters are 1-4"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="month_number", min_value=1, max_value=12,
        meta={"dimension": "Validity", "rationale": "Months are 1-12"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="day_of_week", min_value=1, max_value=7,
        meta={"dimension": "Validity", "rationale": "Day of week 1=Monday ... 7=Sunday (ISO)"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(
        column="day_name", value_set=VALID_DAY_NAMES,
        meta={"dimension": "Validity", "rationale": "Day name must be in ISO weekday enum"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeInSet(
        column="month_name", value_set=VALID_MONTH_NAMES,
        meta={"dimension": "Validity", "rationale": "Month name must be in calendar enum"},
    ))
    suite.add_expectation(gxe.ExpectColumnDistinctValuesToBeInSet(
        column="is_weekend", value_set=[True, False],
        meta={"dimension": "Validity", "rationale": "is_weekend is boolean"},
    ))
    suite.add_expectation(gxe.ExpectColumnDistinctValuesToBeInSet(
        column="is_holiday", value_set=[True, False],
        meta={"dimension": "Validity", "rationale": "is_holiday is boolean"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="date_key", min_value=20_200_101, max_value=20_301_231,
        meta={"dimension": "Validity", "rationale": "date_key is YYYYMMDD integer; range sanity"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="full_date", min_value="2020-01-01", max_value="2030-12-31",
        meta={"dimension": "Validity", "rationale": "full_date within warehouse time horizon"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="year_number",
        meta={"dimension": "Validity", "rationale": "year_number required for year-level rollups"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="quarter_number",
        meta={"dimension": "Validity", "rationale": "quarter_number required for quarterly reports"},
    ))

    # ── Consistency (1) ─────────────────────────────────────────────────────
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT date_key, full_date, month_number "
            "FROM {batch} "
            "WHERE EXTRACT(MONTH FROM full_date) <> month_number"
        ),
        description="month_number must match EXTRACT(MONTH FROM full_date)",
        meta={"dimension": "Consistency",
              "rationale": "Derived attribute must be consistent with the source date column"},
    ))

    return suite


# ---------------------------------------------------------------------------
# 5. fact_sales  (25 expectations)
# ---------------------------------------------------------------------------
def build_fact_sales_suite() -> gx.ExpectationSuite:
    """
    Covers Completeness (6), Uniqueness (2), Validity (10), Consistency (4), Accuracy (2),
    plus 1 additional Validity (order_line_num).
    Predicted FAIL: DQ-007 (#18), DQ-008 (#11).
    """
    suite = gx.ExpectationSuite(name="fact_sales_suite")

    # #1 Row count
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(
        min_value=450_000, max_value=550_000,
        meta={"dimension": "Validity",
              "rationale": "~500,050 rows (500k base + 50 D7 orphan inserts); wide buffer"},
    ))
    # #2 Schema drift guard
    suite.add_expectation(gxe.ExpectTableColumnsToMatchOrderedList(
        column_list=["sales_key", "date_key", "customer_key", "product_key", "store_key",
                     "order_id", "order_line_num", "quantity", "unit_price", "unit_cost",
                     "discount_amount", "net_revenue", "gross_profit", "tax_amount"],
        meta={"dimension": "Validity", "rationale": "14 columns in declared order"},
    ))

    # ── Completeness (6) ────────────────────────────────────────────────────
    for col, rationale in [
        ("sales_key",    "Surrogate PK — structurally required"),
        ("date_key",     "Time dimension FK — required for all temporal analysis"),
        ("customer_key", "Customer FK — required for customer analytics"),
        ("product_key",  "Product FK — required for product analytics"),
        ("store_key",    "Store FK — required for channel analytics"),
        ("net_revenue",  "Primary revenue measure — required for all financial reports"),
    ]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
            column=col,
            meta={"dimension": "Completeness", "rationale": rationale},
        ))

    # ── Uniqueness (2) ──────────────────────────────────────────────────────
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(
        column="sales_key",
        meta={"dimension": "Uniqueness", "rationale": "sales_key is surrogate PK; globally unique"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT order_id, order_line_num, COUNT(*) AS dup_count "
            "FROM {batch} "
            "GROUP BY order_id, order_line_num "
            "HAVING COUNT(*) > 1"
        ),
        description="(order_id, order_line_num) compound key must be unique",
        meta={"dimension": "Uniqueness",
              "rationale": "Duplicate order lines = double-counted revenue risk"},
    ))

    # ── Validity (10) ───────────────────────────────────────────────────────
    # #11 quantity >= 1 — D8 injects 100 rows with quantity=-1 → FAIL (DQ-008)
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="quantity", min_value=1, max_value=10_000,
        meta={"dimension": "Validity",
              "rationale": "Sales rows must have positive quantity; returns handled separately",
              "issue_id": "DQ-008", "predicted": "FAIL"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="unit_price", min_value=0.01, max_value=100_000,
        meta={"dimension": "Validity", "rationale": "Unit price must be positive"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="unit_cost", min_value=0, max_value=100_000,
        meta={"dimension": "Validity", "rationale": "Unit cost >= 0; zero for complimentary goods"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="discount_amount", min_value=0, max_value=50_000,
        meta={"dimension": "Validity", "rationale": "Discount non-negative; upper bound catches bugs"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="net_revenue", min_value=-10_000, max_value=10_000_000,
        meta={"dimension": "Validity",
              "rationale": "Revenue can be slightly negative on heavy-discount transactions"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="gross_profit", min_value=-10_000, max_value=10_000_000,
        meta={"dimension": "Validity",
              "rationale": "Profit can be negative on loss-leader sales (confirmed by profiling)"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="tax_amount", min_value=0, max_value=100_000,
        meta={"dimension": "Validity", "rationale": "Tax must be non-negative"},
    ))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(
        column="order_id", min_value=5, max_value=20,
        meta={"dimension": "Validity",
              "rationale": "order_id length sanity; D7 uses ORD-ORPHAN-#### (16 chars)"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(
        column="order_line_num", min_value=1, max_value=100,
        meta={"dimension": "Validity", "rationale": "Line numbers are 1-indexed positive integers"},
    ))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(
        column="quantity",
        meta={"dimension": "Validity", "rationale": "quantity must never be NULL for a sales fact"},
    ))

    # ── Consistency (4) — cross-table referential integrity ─────────────────
    # #18 customer FK — D7 injects 50 orphan rows → FAIL (DQ-007)
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT f.sales_key, f.customer_key "
            "FROM {batch} f "
            "LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key "
            "WHERE c.customer_key IS NULL"
        ),
        description="fact_sales.customer_key must reference dim_customer.customer_key",
        meta={"dimension": "Consistency",
              "rationale": "D7 injects 50 orphan rows with customer_key=999999",
              "issue_id": "DQ-007", "predicted": "FAIL"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT f.sales_key, f.product_key "
            "FROM {batch} f "
            "LEFT JOIN warehouse.dim_product p ON f.product_key = p.product_key "
            "WHERE p.product_key IS NULL"
        ),
        description="fact_sales.product_key must reference dim_product.product_key",
        meta={"dimension": "Consistency", "rationale": "Referential integrity check"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT f.sales_key, f.store_key "
            "FROM {batch} f "
            "LEFT JOIN warehouse.dim_store s ON f.store_key = s.store_key "
            "WHERE s.store_key IS NULL"
        ),
        description="fact_sales.store_key must reference dim_store.store_key",
        meta={"dimension": "Consistency", "rationale": "Referential integrity check"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT f.sales_key, f.date_key "
            "FROM {batch} f "
            "LEFT JOIN warehouse.dim_date d ON f.date_key = d.date_key "
            "WHERE d.date_key IS NULL"
        ),
        description="fact_sales.date_key must reference dim_date.date_key",
        meta={"dimension": "Consistency", "rationale": "Referential integrity check"},
    ))

    # ── Accuracy (2) — arithmetic invariants ───────────────────────────────
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT sales_key, quantity, unit_price, discount_amount, net_revenue "
            "FROM {batch} "
            "WHERE ABS(net_revenue - (quantity * unit_price - discount_amount)) > 0.01"
        ),
        description="net_revenue ≈ quantity*unit_price - discount_amount (1-cent tolerance)",
        meta={"dimension": "Accuracy",
              "rationale": "Revenue arithmetic invariant; 0.01 tolerance for float rounding"},
    ))
    suite.add_expectation(gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=(
            "SELECT sales_key, quantity, unit_cost, net_revenue, gross_profit "
            "FROM {batch} "
            "WHERE ABS(gross_profit - (net_revenue - (quantity * unit_cost))) > 0.01"
        ),
        description="gross_profit ≈ net_revenue - (quantity*unit_cost) (1-cent tolerance)",
        meta={"dimension": "Accuracy",
              "rationale": "Profit arithmetic invariant; 0.01 tolerance for float rounding"},
    ))

    return suite


# ===========================================================================
# CONTEXT SETUP & RUNNER
# ===========================================================================

SUITE_BUILDERS = {
    "dim_customer": build_dim_customer_suite,
    "dim_product":  build_dim_product_suite,
    "dim_store":    build_dim_store_suite,
    "dim_date":     build_dim_date_suite,
    "fact_sales":   build_fact_sales_suite,
}

ASSET_CONFIG = {
    "dim_customer": {"asset": "dim_customer", "batch": "dim_customer_whole_table"},
    "dim_product":  {"asset": "dim_product",  "batch": "dim_product_whole_table"},
    "dim_store":    {"asset": "dim_store",     "batch": "dim_store_whole_table"},
    "dim_date":     {"asset": "dim_date",      "batch": "dim_date_whole_table"},
    "fact_sales":   {"asset": "fact_sales",    "batch": "fact_sales_whole_table"},
}


def setup_context() -> gx.DataContext:
    """Load (or create) the file-backed GX context."""
    return gx.get_context(mode="file", project_root_dir=str(GX_DIR))


def run_table(context: gx.DataContext, table_name: str) -> dict:
    """Build suite, register it, run validation, return summary dict."""
    print(f"\n{'='*72}")
    print(f"  TABLE: {table_name.upper()}")
    print(f"{'='*72}")

    builder = SUITE_BUILDERS[table_name]
    suite = builder()
    total_exp = len(suite.expectations)
    print(f"  Built suite '{suite.name}' — {total_exp} expectations")

    # Upsert suite
    try:
        context.suites.delete(name=suite.name)
    except Exception:
        pass
    suite = context.suites.add(suite)

    # Locate batch definition
    cfg = ASSET_CONFIG[table_name]
    datasource = context.data_sources.get(DATASOURCE_NAME)
    asset = datasource.get_asset(cfg["asset"])
    batch_def = asset.get_batch_definition(cfg["batch"])

    # Upsert validation definition
    vd_name = f"validate_{table_name}"
    try:
        context.validation_definitions.delete(name=vd_name)
    except Exception:
        pass
    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(name=vd_name, data=batch_def, suite=suite)
    )

    # Run
    result = validation_def.run()

    # Print per-expectation results
    pass_count = fail_count = 0
    print(f"\n  {'#':<3} {'Status':<7} {'Dimension':<15} Expectation")
    print(f"  {'-'*68}")
    for i, r in enumerate(result.results, start=1):
        status = "PASS" if r.success else "FAIL"
        dim = (r.expectation_config.meta or {}).get("dimension", "-")
        etype = getattr(r.expectation_config, "type",
                        getattr(r.expectation_config, "expectation_type", "unknown"))
        marker = "✓" if r.success else "✗"
        print(f"  {i:<3} [{marker}]{status:<6} {dim:<15} {etype}")
        if r.success:
            pass_count += 1
        else:
            fail_count += 1

    print(f"  {'-'*68}")
    print(f"  Summary: {pass_count}/{total_exp} PASS | {fail_count}/{total_exp} FAIL")
    print(f"  Overall success: {result.success}")

    return {
        "table": table_name,
        "total": total_exp,
        "pass": pass_count,
        "fail": fail_count,
        "success": result.success,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Month 4 — Run Great Expectations validation suite"
    )
    parser.add_argument(
        "--table", choices=list(SUITE_BUILDERS.keys()),
        help="Run a single table (default: all tables)"
    )
    args = parser.parse_args()

    context = setup_context()
    tables = [args.table] if args.table else list(SUITE_BUILDERS.keys())

    summaries = []
    for t in tables:
        summaries.append(run_table(context, t))

    # Overall summary
    print(f"\n{'='*72}")
    print("  OVERALL VALIDATION SUMMARY")
    print(f"{'='*72}")
    total_exp = sum(s["total"] for s in summaries)
    total_pass = sum(s["pass"] for s in summaries)
    total_fail = sum(s["fail"] for s in summaries)

    print(f"  {'Table':<20} {'Total':>6} {'PASS':>6} {'FAIL':>6} {'Status'}")
    print(f"  {'-'*55}")
    for s in summaries:
        status = "✅ PASS" if s["success"] else "❌ FAIL"
        print(f"  {s['table']:<20} {s['total']:>6} {s['pass']:>6} {s['fail']:>6}  {status}")
    print(f"  {'-'*55}")
    print(f"  {'TOTAL':<20} {total_exp:>6} {total_pass:>6} {total_fail:>6}")

    # Rebuild Data Docs
    context.build_data_docs()
    docs = GX_DIR / "uncommitted" / "data_docs" / "local_site" / "index.html"
    if docs.exists():
        print(f"\n  Data Docs: file://{docs}")

    print(f"\n  Run complete. Total: {total_pass}/{total_exp} PASS.")


if __name__ == "__main__":
    main()
