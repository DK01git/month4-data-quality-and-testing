# Data Validation Report
## RetailCo Retail Data Warehouse — Month 4

**Author:** Diluksha Perera  
**Date:** 2026-04-29  
**Database:** `retaildw_dq` (mirror with injected defects)  
**GX Version:** great-expectations 1.x (file-backed context)  
**Total Expectations Run:** 114 across 5 tables

---

## 1. Executive Summary

The Great Expectations validation suite was executed against the mirror database `retaildw_dq.warehouse`, which contains all eight synthetic defects (D1–D8) injected to simulate real production quality issues documented in the challenge brief.

| Metric | Value |
|--------|-------|
| Total expectations run | 114 |
| Total PASS | 106 |
| Total FAIL | 8 |
| Overall pass rate | **93.0%** |
| Tables with zero failures | 2 (dim_date, dim_store) |
| Critical failures | 2 (DQ-002, DQ-007) |
| High failures | 4 (DQ-001, DQ-003, DQ-005, DQ-008) |
| Medium failures | 2 (DQ-004, DQ-006) |

All 8 failures were **predicted by the suite design** — each maps directly to an injected defect. The validation suite behaved exactly as intended: it caught every known issue without generating false positives on clean tables.

---

## 2. Per-Table Validation Results

### 2.1 dim_customer — 28 expectations

| # | Status | Dimension | Expectation | Predicted? | Issue ID |
|---|--------|-----------|-------------|-----------|----------|
| 1 | ✅ PASS | Validity | expect_table_row_count_to_be_between (9k–11k) | — | — |
| 2 | ✅ PASS | Validity | expect_table_columns_to_match_ordered_list | — | — |
| 3 | ✅ PASS | Completeness | customer_key NOT NULL | — | — |
| 4 | ✅ PASS | Completeness | customer_id NOT NULL | — | — |
| 5 | ✅ PASS | Completeness | customer_name NOT NULL | — | — |
| 6 | ✅ PASS | Completeness | effective_date NOT NULL | — | — |
| 7 | ✅ PASS | Completeness | expiry_date NOT NULL | — | — |
| 8 | ✅ PASS | Completeness | is_current NOT NULL | — | — |
| 9 | ❌ FAIL | Completeness | email NOT NULL (mostly=0.99) | ✓ | **DQ-001** |
| 10 | ✅ PASS | Uniqueness | customer_key unique | — | — |
| 11 | ✅ PASS | Uniqueness | (customer_id, effective_date) compound unique | — | — |
| 12 | ❌ FAIL | Uniqueness | SQL: one is_current=TRUE per customer_id | ✓ | **DQ-002** |
| 13 | ❌ FAIL | Validity | email regex match (mostly=0.99) | ✓ | **DQ-003** |
| 14 | ❌ FAIL | Validity | customer_segment in enum | ✓ | **DQ-004** |
| 15 | ✅ PASS | Validity | customer_id format ^CUS[0-9]+$ | — | — |
| 16 | ✅ PASS | Validity | customer_id length 5–15 | — | — |
| 17 | ✅ PASS | Validity | customer_name length 3–50 | — | — |
| 18 | ✅ PASS | Validity | email length 5–100 (mostly=0.95) | — | — |
| 19 | ✅ PASS | Validity | zip_code 10000–99999 | — | — |
| 20 | ✅ PASS | Validity | state length = 2 | — | — |
| 21 | ✅ PASS | Validity | effective_date 2020-01-01–2030-12-31 | — | — |
| 22 | ✅ PASS | Validity | customer_key 1–200000 | — | — |
| 23 | ✅ PASS | Validity | customer_segment length 5–20 | — | — |
| 24 | ✅ PASS | Validity | is_current in {TRUE, FALSE} | — | — |
| 25 | ✅ PASS | Validity | expiry_date range | — | — |
| 26 | ✅ PASS | Validity | city length 2–50 | — | — |
| 27 | ✅ PASS | Consistency | expiry_date >= effective_date | — | — |
| 28 | ✅ PASS | Consistency | is_current=TRUE rows → expiry_date = 9999-12-31 | — | — |

**dim_customer summary: 24 PASS / 4 FAIL**

**Failure details:**

- **DQ-001** — `email` null rate = 3.0% (300/10,010 rows). Exceeds the 1% budget (`mostly=0.99`). Root cause: CRM migration cleared opt-out emails without sentinel substitution.
- **DQ-002** — 10 customer_ids with 2 is_current=TRUE rows each. The SCD2 merge procedure has a race condition under concurrent load.
- **DQ-003** — `email` regex failures: 300 NULLs (treated as non-matching by default) + 200 literal `'n/a'` values = 500 non-matching out of 10,010 rows (~5%). Exceeds the 1% tolerance.
- **DQ-004** — 50 rows with `customer_segment = 'Platnium'` (typo for 'Premium'). Not in approved enum `{Standard, Budget, Premium}`.

---

### 2.2 dim_product — 21 expectations

| # | Status | Dimension | Expectation | Predicted? | Issue ID |
|---|--------|-----------|-------------|-----------|----------|
| 1 | ✅ PASS | Validity | row count 800–1200 | — | — |
| 2 | ✅ PASS | Validity | schema columns ordered | — | — |
| 3 | ✅ PASS | Completeness | product_key NOT NULL | — | — |
| 4 | ✅ PASS | Completeness | product_id NOT NULL | — | — |
| 5 | ✅ PASS | Completeness | product_name NOT NULL | — | — |
| 6 | ✅ PASS | Completeness | is_active NOT NULL | — | — |
| 7 | ✅ PASS | Completeness | list_price NOT NULL | — | — |
| 8 | ✅ PASS | Uniqueness | product_key unique | — | — |
| 9 | ✅ PASS | Uniqueness | product_id unique | — | — |
| 10 | ❌ FAIL | Validity | list_price between 0.01–100000 | ✓ | **DQ-005** |
| 11 | ✅ PASS | Validity | cost_price between 0–100000 | — | — |
| 12 | ✅ PASS | Validity | product_key range | — | — |
| 13 | ✅ PASS | Validity | product_id length | — | — |
| 14 | ✅ PASS | Validity | product_name length | — | — |
| 15 | ✅ PASS | Validity | is_active boolean | — | — |
| 16 | ✅ PASS | Validity | category NOT NULL | — | — |
| 17 | ✅ PASS | Validity | category length | — | — |
| 18 | ✅ PASS | Validity | brand NOT NULL | — | — |
| 19 | ✅ PASS | Validity | brand length | — | — |
| 20 | ✅ PASS | Validity | product_id format ^PROD[0-9]+$ | — | — |
| 21 | ❌ FAIL | Accuracy | cost_price < list_price (where list_price > 0) | ✓ | **DQ-006** |

**dim_product summary: 19 PASS / 2 FAIL**

**Failure details:**

- **DQ-005** — 15 rows have `list_price = 0.00`. These were imported during a promotional batch import that did not apply a fallback standard price. Fails the `min_value=0.01` check.
- **DQ-006** — 10 rows have `cost_price >= list_price` (excluding the 15 zero-price rows to avoid double-counting). These products show negative margin in analytics dashboards.

---

### 2.3 dim_store — 20 expectations

| # | Status | Dimension | Expectation |
|---|--------|-----------|-------------|
| 1–20 | ✅ PASS | All | All expectations passed |

**dim_store summary: 20 PASS / 0 FAIL**

No defects were injected into `dim_store`. The opening_date range check (`≤ 2026-12-31`) acts as a forward defence against future data entry errors (a known production risk per the challenge brief, DQ scenario: 5 stores with opening_date in the future — not present in the synthetic dataset but the expectation guards against it).

---

### 2.4 dim_date — 20 expectations

| # | Status | Dimension | Expectation |
|---|--------|-----------|-------------|
| 1–20 | ✅ PASS | All | All expectations passed |

**dim_date summary: 20 PASS / 0 FAIL**

The date dimension is a static, generated table. Consistency check (`EXTRACT(MONTH FROM full_date) = month_number`) confirmed all derived attributes are correct.

---

### 2.5 fact_sales — 25 expectations

| # | Status | Dimension | Expectation | Predicted? | Issue ID |
|---|--------|-----------|-------------|-----------|----------|
| 1 | ✅ PASS | Validity | row count 450k–550k | — | — |
| 2 | ✅ PASS | Validity | schema columns ordered | — | — |
| 3 | ✅ PASS | Completeness | sales_key NOT NULL | — | — |
| 4 | ✅ PASS | Completeness | date_key NOT NULL | — | — |
| 5 | ✅ PASS | Completeness | customer_key NOT NULL | — | — |
| 6 | ✅ PASS | Completeness | product_key NOT NULL | — | — |
| 7 | ✅ PASS | Completeness | store_key NOT NULL | — | — |
| 8 | ✅ PASS | Completeness | net_revenue NOT NULL | — | — |
| 9 | ✅ PASS | Uniqueness | sales_key unique | — | — |
| 10 | ✅ PASS | Uniqueness | (order_id, order_line_num) unique | — | — |
| 11 | ❌ FAIL | Validity | quantity between 1–10000 | ✓ | **DQ-008** |
| 12 | ✅ PASS | Validity | unit_price 0.01–100000 | — | — |
| 13 | ✅ PASS | Validity | unit_cost 0–100000 | — | — |
| 14 | ✅ PASS | Validity | discount_amount 0–50000 | — | — |
| 15 | ✅ PASS | Validity | net_revenue -10000–10000000 | — | — |
| 16 | ✅ PASS | Validity | gross_profit -10000–10000000 | — | — |
| 17 | ✅ PASS | Validity | tax_amount 0–100000 | — | — |
| 18 | ❌ FAIL | Consistency | customer_key → dim_customer (FK) | ✓ | **DQ-007** |
| 19 | ✅ PASS | Consistency | product_key → dim_product (FK) | — | — |
| 20 | ✅ PASS | Consistency | store_key → dim_store (FK) | — | — |
| 21 | ✅ PASS | Consistency | date_key → dim_date (FK) | — | — |
| 22 | ✅ PASS | Accuracy | net_revenue = qty*price - discount (±0.01) | — | — |
| 23 | ✅ PASS | Accuracy | gross_profit = net_revenue - qty*cost (±0.01) | — | — |
| 24 | ✅ PASS | Validity | order_id length 5–20 | — | — |
| 25 | ✅ PASS | Validity | order_line_num 1–100 | — | — |

**fact_sales summary: 23 PASS / 2 FAIL**

**Failure details:**

- **DQ-008** — 100 rows with `quantity = -1`. These are return transactions mixed into the sales table. The `min_value=1` check correctly flags them. They inflate refund exposure and understate gross units sold.
- **DQ-007** — 50 rows with `customer_key = 999999` which does not exist in `dim_customer`. Revenue from these transactions cannot be attributed to any customer segment. The LEFT JOIN IS NULL pattern correctly identifies all 50 orphans.

---

## 3. Validation Summary Table

| Table | Expectations | PASS | FAIL | Pass Rate | Status |
|-------|-------------|------|------|-----------|--------|
| dim_date | 20 | 20 | 0 | 100.0% | ✅ PASS |
| dim_store | 20 | 20 | 0 | 100.0% | ✅ PASS |
| dim_product | 21 | 19 | 2 | 90.5% | ❌ FAIL |
| dim_customer | 28 | 24 | 4 | 85.7% | ❌ FAIL |
| fact_sales | 25 | 23 | 2 | 92.0% | ❌ FAIL |
| **TOTAL** | **114** | **106** | **8** | **93.0%** | **❌ FAIL** |

---

## 4. Defect Coverage Report

| Defect | Table | Rows Affected | Dimension | GX Expectation(s) | Caught? |
|--------|-------|:------------:|-----------|-------------------|:-------:|
| D1 | dim_customer | 300 | Completeness | email NOT NULL (mostly=0.99) | ✅ Yes |
| D2 | dim_customer | 10 | Uniqueness | SQL: SCD2 current-row count per customer_id | ✅ Yes |
| D3 | dim_customer | 200 | Validity | email regex (mostly=0.99) | ✅ Yes |
| D4 | dim_customer | 50 | Validity | customer_segment enum check | ✅ Yes |
| D5 | dim_product | 15 | Validity | list_price min_value=0.01 | ✅ Yes |
| D6 | dim_product | 10 | Accuracy | SQL: cost_price >= list_price check | ✅ Yes |
| D7 | fact_sales | 50 | Consistency | SQL LEFT JOIN IS NULL (customer FK) | ✅ Yes |
| D8 | fact_sales | 100 | Validity | quantity min_value=1 | ✅ Yes |

**Detection rate: 8/8 (100%)**

---

## 5. Remediation Procedures

### 5.1 DQ-001 — NULL Emails (PRIORITY: High)

**Immediate action (hotfix):**
```sql
-- Count affected rows
SELECT COUNT(*) FROM warehouse.dim_customer WHERE email IS NULL;

-- Option A: Set a null-safe sentinel for opt-out emails
UPDATE warehouse.dim_customer
SET email = 'optout@retailco.internal'
WHERE email IS NULL;

-- Option B: Leave as NULL but fix the upstream CRM mapping
-- (coordinate with source system team)
```

**Long-term fix:** Modify the CRM-to-warehouse ingestion transform to distinguish between `null` (unknown) and `optout` (known opt-out). Add a separate `email_status` column with values `{active, optout, unknown}`.

**Validation gate:** After fix, re-run `dim_customer_suite`. Expect expectation #9 to PASS.

---

### 5.2 DQ-002 — Duplicate SCD2 Current Rows (PRIORITY: Critical)

**Immediate action (data repair):**
```sql
-- Identify affected customer_ids
SELECT customer_id, COUNT(*) AS current_row_count
FROM warehouse.dim_customer
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- For each duplicate, keep the most recent record and expire older ones
UPDATE warehouse.dim_customer
SET is_current = FALSE,
    expiry_date = CURRENT_DATE - INTERVAL '1 day'
WHERE customer_key IN (
    SELECT customer_key
    FROM (
        SELECT customer_key,
               ROW_NUMBER() OVER (
                   PARTITION BY customer_id
                   ORDER BY effective_date DESC
               ) AS rn
        FROM warehouse.dim_customer
        WHERE is_current = TRUE
    ) ranked
    WHERE rn > 1
);
```

**Long-term fix:** Add `SELECT ... FOR UPDATE SKIP LOCKED` advisory locking to the SCD2 merge procedure in Airflow. Alternatively, use a staging lock table to serialise concurrent SCD2 writes.

**Validation gate:** After fix, re-run expectations #12 and #27. Both should PASS.

---

### 5.3 DQ-003 — 'n/a' Email Sentinel (PRIORITY: High)

**Immediate action:**
```sql
-- Convert 'n/a' sentinel to NULL (or the optout email if using Option A from DQ-001 fix)
UPDATE warehouse.dim_customer
SET email = NULL
WHERE email = 'n/a';
```

**Long-term fix:** Add an ingestion-layer transform rule: `CASE WHEN email IN ('n/a', 'N/A', 'na', 'NA', '') THEN NULL ELSE email END`. Extend the data contract to explicitly prohibit these sentinel strings.

---

### 5.4 DQ-004 — Segment Enum Typo 'Platnium' (PRIORITY: Medium)

**Immediate action:**
```sql
-- Fix the typo
UPDATE warehouse.dim_customer
SET customer_segment = 'Premium'
WHERE customer_segment = 'Platnium';
```

**Long-term fix:** Enforce dropdown validation in the source CRM before data leaves the system. Add an enum check in the ingestion layer's dbt source test.

---

### 5.5 DQ-005 — Zero List Price (PRIORITY: High)

**Immediate action:**
```sql
-- Identify zero-price products
SELECT product_key, product_id, product_name, list_price
FROM warehouse.dim_product
WHERE list_price <= 0;

-- Join to pricing master to backfill standard prices
-- (requires coordination with source ERP team)
UPDATE warehouse.dim_product p
SET list_price = ep.standard_price
FROM source.erp_product_master ep
WHERE p.product_id = ep.product_id
AND p.list_price <= 0;
```

**Long-term fix:** Add a `list_price > 0` validation in the product import script before data enters the staging layer.

---

### 5.6 DQ-006 — Cost Exceeds List Price (PRIORITY: Medium)

**Immediate action:**
```sql
-- Identify affected products
SELECT product_key, product_id, product_name, list_price, cost_price,
       cost_price - list_price AS margin_deficit
FROM warehouse.dim_product
WHERE cost_price >= list_price AND list_price > 0
ORDER BY margin_deficit DESC;
```

**Long-term fix:** Add a cross-field validation in the product master update workflow: reject any cost_price update where `new_cost >= current_list_price` without manager approval.

---

### 5.7 DQ-007 — Orphan FK Rows in fact_sales (PRIORITY: Critical)

**Immediate action:**
```sql
-- Quarantine orphan rows to a holding table for investigation
BEGIN;

CREATE TABLE IF NOT EXISTS warehouse.fact_sales_orphan_quarantine
    AS SELECT *, NOW() AS quarantined_at
    FROM warehouse.fact_sales WHERE 1=0;

INSERT INTO warehouse.fact_sales_orphan_quarantine
SELECT f.*, NOW() AS quarantined_at
FROM warehouse.fact_sales f
LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key
WHERE c.customer_key IS NULL;

DELETE FROM warehouse.fact_sales
WHERE sales_key IN (SELECT sales_key FROM warehouse.fact_sales_orphan_quarantine);

COMMIT;
```

**Long-term fix:** Add a staging-layer referential integrity check in the ETL DAG before promoting data to the gold layer. The check must verify all FK values exist in dimension tables *after* the dimension load task completes and *before* the fact load begins. Use Airflow task dependencies to enforce this ordering.

**Validation gate:** After fix, expectation #18 should return 0 unexpected rows.

---

### 5.8 DQ-008 — Negative Quantity Sales (PRIORITY: High)

**Immediate action:**
```sql
-- Move return rows to a separate fact_returns table
BEGIN;

CREATE TABLE IF NOT EXISTS warehouse.fact_returns
    AS SELECT *, NOW() AS quarantined_at
    FROM warehouse.fact_sales WHERE 1=0;

INSERT INTO warehouse.fact_returns
SELECT *, NOW() AS quarantined_at
FROM warehouse.fact_sales
WHERE quantity < 1;

DELETE FROM warehouse.fact_sales
WHERE quantity < 1;

COMMIT;
```

**Long-term fix:** The order management system should separate sales (quantity > 0) and returns (quantity < 0) at the source by using a `transaction_type` column with values `{SALE, RETURN, EXCHANGE}`. The ETL should route each type to its respective fact table.

---

## 6. Anomaly Detection Strategy

### 6.1 Volume Anomaly Detection

Statistical thresholds are more robust than fixed-count rules because they adapt to seasonality (e.g., Black Friday spikes, January lulls).

```sql
-- Anomaly detection query (runs nightly after ETL)
-- Uses two windows:
--   7-day rolling avg  → primary threshold: alert if today < 7d_avg * 0.5
--   30-day rolling avg → z-score baseline for statistical detection (3-sigma rule)
WITH daily_volumes AS (
    SELECT
        load_date,
        COUNT(*) AS row_count
    FROM warehouse.fact_sales
    WHERE load_date >= CURRENT_DATE - INTERVAL '31 days'
    GROUP BY load_date
),
rolling_windows AS (
    SELECT
        load_date,
        row_count,
        -- 7-day rolling average (primary SLA threshold per challenge spec)
        AVG(row_count) OVER (
            ORDER BY load_date
            ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
        ) AS rolling_7d_avg,
        -- 30-day rolling stddev (for z-score / 3-sigma detection)
        AVG(row_count) OVER (
            ORDER BY load_date
            ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING
        ) AS rolling_30d_avg,
        STDDEV(row_count) OVER (
            ORDER BY load_date
            ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING
        ) AS rolling_30d_stddev
    FROM daily_volumes
)
SELECT
    load_date,
    row_count,
    ROUND(rolling_7d_avg,  0)  AS rolling_7d_avg,
    ROUND(rolling_30d_avg, 0)  AS rolling_30d_avg,
    ROUND(rolling_7d_avg * 0.5, 0)  AS lower_bound_50pct,   -- primary SLA gate
    ROUND((row_count - rolling_30d_avg) / NULLIF(rolling_30d_stddev, 0), 2) AS z_score,
    CASE
        WHEN row_count < rolling_7d_avg * 0.5
            THEN 'SEVERE_DROP — possible partial load (< 50% of 7-day avg)'
        WHEN ABS((row_count - rolling_30d_avg)
                 / NULLIF(rolling_30d_stddev, 0)) > 3
            THEN 'STATISTICAL_ANOMALY — beyond 3-sigma boundary'
        WHEN row_count > rolling_7d_avg * 1.5
            THEN 'HIGH_VOLUME — check for duplicate inserts'
        ELSE 'NORMAL'
    END AS anomaly_flag
FROM rolling_windows
WHERE load_date = CURRENT_DATE;
```

**Alert thresholds:**

| Signal | Condition | Severity |
|--------|-----------|----------|
| Partial load | `row_count < rolling_7d_avg * 0.5` | High |
| Statistical anomaly | `\|z_score\| > 3` (3-sigma rule) | High |
| Duplicate suspect | `row_count > rolling_7d_avg * 1.5` | Medium |

### 6.2 Freshness Anomaly Detection

```sql
-- Check if daily ETL landed on time (SLA = before 06:00 UTC)
SELECT
    CURRENT_DATE AS check_date,
    MAX(load_timestamp) AS last_load,
    EXTRACT(EPOCH FROM (NOW() - MAX(load_timestamp))) / 3600 AS hours_since_load,
    CASE
        WHEN MAX(load_timestamp) < CURRENT_DATE + TIME '06:00:00' THEN 'SLA_MET'
        ELSE 'SLA_BREACH'
    END AS sla_status
FROM warehouse.etl_load_log
WHERE table_name = 'fact_sales'
AND load_date = CURRENT_DATE;
```

### 6.3 Revenue Anomaly Detection

```sql
-- Daily revenue vs 30-day rolling average
WITH daily_revenue AS (
    SELECT
        date_key,
        SUM(net_revenue)   AS total_revenue,
        COUNT(*)           AS row_count
    FROM warehouse.fact_sales
    GROUP BY date_key
),
stats AS (
    SELECT
        date_key,
        total_revenue,
        AVG(total_revenue) OVER (
            ORDER BY date_key
            ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING
        ) AS rolling_30d_avg,
        STDDEV(total_revenue) OVER (
            ORDER BY date_key
            ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING
        ) AS rolling_30d_std
    FROM daily_revenue
)
SELECT
    date_key,
    total_revenue,
    ROUND(rolling_30d_avg, 2) AS expected_avg,
    ROUND((total_revenue - rolling_30d_avg) / NULLIF(rolling_30d_std, 0), 2) AS z_score,
    CASE
        WHEN ABS((total_revenue - rolling_30d_avg) / NULLIF(rolling_30d_std, 0)) > 3
        THEN 'REVENUE_ANOMALY — investigate'
        ELSE 'NORMAL'
    END AS anomaly_flag
FROM stats
ORDER BY date_key DESC
LIMIT 10;
```

---

## 7. Airflow Integration Plan

The following DAG structure integrates GX validations into the existing ETL pipeline (shift-left pattern):

```
[Source Extract]
      │
      ▼
[Staging Load]
      │
      ▼
[dim_* Validation]  ◄── Great Expectations checkpoints per dimension table
      │                  (FAIL → quarantine + alert; do not promote to gold)
      ▼
[dim_* Gold Promote]
      │
      ▼
[fact_sales Staging FK Check]  ◄── Referential integrity SQL (pre-promotion)
      │                             (FAIL → quarantine orphans + alert)
      ▼
[fact_sales Validation]  ◄── Great Expectations fact_sales_suite
      │                       (FAIL → alert but allow partial load for non-critical)
      ▼
[fact_sales Gold Promote]
      │
      ▼
[Quality Metrics Update]  ◄── Write pass/fail counts to quality_metrics schema
      │
      ▼
[Data Docs Rebuild]  ◄── HTML report regenerated for stakeholder review
      │
      ▼
[Dashboard Refresh Trigger]
```

**Key design decisions:**
- Dimension validations are **blocking** — a dim failure stops the fact load (prevents orphan FK creation).
- Fact validations are **non-blocking for non-critical failures** — HIGH/MEDIUM issues alert but allow the load to proceed. CRITICAL failures (orphan FKs, arithmetic errors) quarantine affected rows.
- Every validation result writes to `quality_metrics.validation_runs` regardless of pass/fail — this builds the trend history needed for the dashboard.

---

## 8. Data Docs Report Note

After running `python diluksha-month4-ge-suite.py`, the GX Data Docs HTML report is generated at:

```
gx\uncommitted\data_docs\local_site\index.html
```

Open this file in a browser to review the full interactive validation report, including:
- Per-expectation PASS/FAIL with observed vs expected values
- Unexpected row samples for SQL-based expectations
- Historical run comparison (if multiple runs have been executed)

---

*Validation report for Month 4 Data Engineering Training — RetailCo Retail Data Warehouse.*
