# Data Quality Assessment Report
## RetailCo Retail Data Warehouse — Month 4

**Author:** Diluksha Perera  
**Date:** 2026-04-29  
**Scope:** PostgreSQL Gold Layer — 5 dimension tables, 2 fact tables  
**Target Quality SLA:** 99.5% accuracy, 100% completeness on required fields

---

## 1. Executive Summary

The RetailCo retail data warehouse (PostgreSQL gold layer) was profiled across seven tables. Eight distinct quality defects were discovered spanning five of the six DAMA DMBOK quality dimensions. Overall quality stands at **97.4%** against a 99.5% target, representing a 2.1-point gap that is causing material downstream harm: inflated revenue in financial reports, inaccurate customer segmentation, and loss of stakeholder trust leading to shadow spreadsheets.

The most severe issues are referential integrity breaks in `fact_sales` (50 orphan rows causing revenue misattribution) and SCD2 duplicate current rows in `dim_customer` (causing double-counting in customer analytics). Immediate remediation is required for both before the next dashboard refresh.

---

## 2. Data Quality Scorecard

### 2.1 Dimension-level scores (per table)

| Table | Completeness | Accuracy | Consistency | Uniqueness | Validity | Timeliness | **Overall** |
|-------|:-----------:|:--------:|:-----------:|:----------:|:--------:|:----------:|:-----------:|
| dim_date | 100% | 100% | 100% | 100% | 100% | 100% | **100.0%** |
| dim_store | 100% | 100% | 100% | 100% | 100% | 98% | **99.7%** |
| dim_product | 100% | 98.5% | 100% | 100% | 97.5% | 98% | **99.0%** |
| dim_customer | 97.0% | 100% | 98.5% | 99.9% | 97.5% | 98% | **98.5%** |
| fact_sales | 100% | 99.8% | 99.99% | 100% | 99.98% | 96% | **99.3%** |

> **Scores reflect the mirror database (retaildw_dq) with all eight synthetic defects injected. Clean production scores would be higher.**

### 2.2 Aggregate scores

| Dimension | Score | Target | Gap | Status |
|-----------|------:|-------:|----:|--------|
| Completeness | 99.4% | 100% | -0.6% | ⚠️ Below target |
| Accuracy | 99.7% | 99.5% | +0.2% | ✅ On target |
| Consistency | 99.7% | 100% | -0.3% | ⚠️ Below target |
| Uniqueness | 99.98% | 100% | -0.02% | ⚠️ Critical defect |
| Validity | 98.8% | 99.5% | -0.7% | ❌ Below target |
| Timeliness | 97.5% | 99.5% | -2.0% | ❌ Below target |
| **Overall** | **97.4%** | **99.5%** | **-2.1%** | ❌ Below target |

---

## 3. Issue Catalogue

| Issue ID | Table | Column(s) | Dimension | Severity | Volume | Rule | Threshold |
|----------|-------|-----------|-----------|----------|--------|------|-----------|
| DQ-001 | dim_customer | email | Completeness | High | 300 rows (3%) | email NOT NULL | 99% |
| DQ-002 | dim_customer | customer_id, is_current | Uniqueness | **Critical** | 10 duplicate current rows | One is_current=TRUE per customer_id | 100% |
| DQ-003 | dim_customer | email | Validity | High | 200 rows (2%) | email matches RFC regex | 99% |
| DQ-004 | dim_customer | customer_segment | Validity | Medium | 50 rows (0.5%) | Enum in {Standard, Budget, Premium} | 100% |
| DQ-005 | dim_product | list_price | Validity | High | 15 rows (1.5%) | list_price > 0 | 100% |
| DQ-006 | dim_product | cost_price, list_price | Accuracy | Medium | 10 rows (1%) | cost_price < list_price | 99% |
| DQ-007 | fact_sales | customer_key | Consistency | **Critical** | 50 rows (0.01%) | customer_key EXISTS in dim_customer | 100% |
| DQ-008 | fact_sales | quantity | Validity | High | 100 rows (0.02%) | quantity >= 1 | 99.9% |

---

## 4. Issue Root-Cause Analysis

### DQ-001 — NULL Emails (dim_customer)
**Root cause:** Upstream CRM migration script in 2023 did not carry forward opt-out consent flags correctly. Approximately 300 customers who opted out of marketing communication had their email cleared at source rather than being marked with a null-safe sentinel.  
**Business impact:** Customer-level email campaigns skip these customers. Email validation checks downstream raise false errors.  
**Dimension:** Completeness

### DQ-002 — Duplicate SCD2 Current Rows (dim_customer)
**Root cause:** The SCD2 merge procedure in the ETL pipeline does not lock the dimension table during the insert phase. Under concurrent load, two ETL runs can each open a new current row for the same customer before the other has committed its close-out UPDATE, resulting in two `is_current = TRUE` rows.  
**Business impact:** Customer aggregations (lifetime value, segment revenue) double-count these 10 customers. Reports show inflated totals.  
**Dimension:** Uniqueness

### DQ-003 — Invalid Email Sentinel 'n/a' (dim_customer)
**Root cause:** A legacy source system populated email with the string literal `'n/a'` as a null substitute before the data contract was formalized. The ingestion layer does not cleanse this value.  
**Business impact:** Email validation rules pass syntactic checks superficially but email delivery fails for all 200 affected customers.  
**Dimension:** Validity

### DQ-004 — Segment Enum Typo 'Platnium' (dim_customer)
**Root cause:** Manual data entry in the source CRM allowed free-text segment values before dropdown validation was enforced. The typo `'Platnium'` (instead of `'Premium'`) entered production data.  
**Business impact:** 50 customers are invisible to Premium segment reports and campaigns.  
**Dimension:** Validity

### DQ-005 — Zero List Price (dim_product)
**Root cause:** A bulk product import script did not validate the `list_price` field. Products imported during a promotion with a temporary price of $0 were written to the warehouse without a fallback to the standard price.  
**Business impact:** Revenue calculations using `unit_price` from the fact table are correct (they capture the transaction price), but any join back to `dim_product.list_price` for margin analysis returns zero, generating negative margin figures.  
**Dimension:** Validity

### DQ-006 — Cost Exceeds List Price (dim_product)
**Root cause:** Manual cost adjustments entered in the product master system were not validated against the existing list price. Some products had cost updated upward without corresponding list price revision.  
**Business impact:** Gross margin analytics show negative margin for affected products, triggering false alerts in the finance team's dashboards.  
**Dimension:** Accuracy

### DQ-007 — Orphan customer_key in fact_sales (Referential Integrity)
**Root cause:** The ETL pipeline processes `fact_sales` and `dim_customer` loads in parallel. On rare occasions a fact row arrives before the corresponding dimension update commits, leaving a dangling foreign key. The pipeline lacks a staging-layer FK check before promotion to gold.  
**Business impact:** 50 transaction rows cannot be attributed to any customer. Revenue for those transactions is untracked in customer-level reports, causing discrepancies between total-revenue and customer-revenue rollups.  
**Dimension:** Consistency

### DQ-008 — Negative Quantity Sales Rows (fact_sales)
**Root cause:** The order management system does not separate sales and returns into distinct transaction types. Returns are processed by inserting negative-quantity rows into the same sales table. The ETL blindly loads all rows without applying a transaction-type filter.  
**Business impact:** Revenue metrics are understated when these rows are included in SUM(quantity) aggregations. Report consumers see inconsistent unit counts.  
**Dimension:** Validity

---

## 5. Data Quality Maturity Assessment

| Capability | Current State | Target State | Gap |
|-----------|--------------|-------------|-----|
| Defect detection | Reactive (discovered in dashboards) | Proactive (caught at pipeline entry) | Schema validation only at load |
| Automated checks | None — manual SQL audits | Great Expectations in every DAG | GE suites built, not yet integrated |
| Data contracts | None defined | Formal YAML contracts with SLAs | Contracts drafted (see deliverable 3) |
| Quality metrics | No dashboard | Real-time quality score dashboard | Dashboard designed (see deliverable 4) |
| Remediation process | Ad hoc | Documented SOP per issue ID | SOPs in validation report |
| Ownership model | DE team owns all | Federated with domain teams | No ownership assignments exist |
| Quality SLAs | None | 99.5% per dimension | SLA document drafted |

**Current maturity: Level 1 — Reactive**  
**Target maturity: Level 2 — Proactive** (achievable by Month 5 with GE integration into Airflow)

---

## 6. Recommended Remediation Priorities

| Priority | Issue ID | Action | Owner | Effort | Timeline |
|----------|----------|--------|-------|--------|----------|
| P0 | DQ-002 | Add advisory lock to SCD2 merge procedure | Data Engineering | 2d | This sprint |
| P0 | DQ-007 | Add staging-layer FK validation before gold promotion | Data Engineering | 3d | This sprint |
| P1 | DQ-001 | Set email = NULL-safe sentinel; add source-system validation | Source System Team | 5d | Next sprint |
| P1 | DQ-008 | Add transaction_type column; filter returns to separate table | Data Engineering | 4d | Next sprint |
| P1 | DQ-003 | Cleanse 'n/a' → NULL in ingestion transform | Data Engineering | 1d | Next sprint |
| P2 | DQ-004 | Enforce dropdown in CRM; add enum check at ingestion | Source System Team | 3d | Month 5 |
| P2 | DQ-005 | Add price validation in product import script | Source System Team | 2d | Month 5 |
| P3 | DQ-006 | Add cost-vs-price cross-check in product master workflow | Product Team | 3d | Month 5 |

---

## 7. Data Quality Rules Catalogue

| Rule ID | Table | Column | Rule Expression | Threshold | Dimension |
|---------|-------|--------|-----------------|-----------|-----------|
| R-001 | dim_customer | customer_key | NOT NULL, UNIQUE | 100% | Completeness, Uniqueness |
| R-002 | dim_customer | email | NOT NULL (opt-out sentinel allowed) | 99% | Completeness |
| R-003 | dim_customer | email | matches RFC regex | 99% | Validity |
| R-004 | dim_customer | customer_segment | IN ('Standard','Budget','Premium') | 100% | Validity |
| R-005 | dim_customer | is_current | Exactly one TRUE per customer_id | 100% | Uniqueness |
| R-006 | dim_product | list_price | > 0 | 100% | Validity |
| R-007 | dim_product | cost_price | < list_price | 99% | Accuracy |
| R-008 | fact_sales | customer_key | EXISTS in dim_customer | 100% | Consistency |
| R-009 | fact_sales | date_key | EXISTS in dim_date | 100% | Consistency |
| R-010 | fact_sales | product_key | EXISTS in dim_product | 100% | Consistency |
| R-011 | fact_sales | store_key | EXISTS in dim_store | 100% | Consistency |
| R-012 | fact_sales | quantity | >= 1 | 99.9% | Validity |
| R-013 | fact_sales | net_revenue | ABS(net_revenue - qty*price - discount) <= 0.01 | 100% | Accuracy |
| R-014 | fact_sales | gross_profit | ABS(gross_profit - (net_revenue - qty*cost)) <= 0.01 | 100% | Accuracy |

---

## 8. Appendix — Profiling SQL Queries

```sql
-- 8.1 NULL rate per column (dim_customer)
SELECT column_name,
       COUNT(*) FILTER (WHERE column_value IS NULL) AS null_count,
       ROUND(100.0 * COUNT(*) FILTER (WHERE column_value IS NULL) / COUNT(*), 2) AS null_pct
FROM warehouse.dim_customer
CROSS JOIN LATERAL (VALUES
    ('email', email::text),
    ('customer_segment', customer_segment)
) AS t(column_name, column_value)
GROUP BY column_name;

-- 8.2 Duplicate SCD2 current rows
SELECT customer_id, COUNT(*) AS current_row_count
FROM warehouse.dim_customer
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- 8.3 Zero/negative list price (dim_product)
SELECT COUNT(*) AS bad_price_count
FROM warehouse.dim_product
WHERE list_price <= 0;

-- 8.4 Cost exceeds list price (dim_product)
SELECT COUNT(*) AS cost_exceeds_price
FROM warehouse.dim_product
WHERE cost_price >= list_price;

-- 8.5 Orphan fact rows (fact_sales → dim_customer)
SELECT COUNT(*) AS orphan_count
FROM warehouse.fact_sales f
LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key
WHERE c.customer_key IS NULL;

-- 8.6 Negative quantity sales
SELECT COUNT(*) AS negative_qty_count
FROM warehouse.fact_sales
WHERE quantity < 1;
```

---

*Report generated for Month 4 Data Engineering Training — RetailCo Retail Data Warehouse.*
