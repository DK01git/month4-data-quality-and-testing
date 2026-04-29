# Month 4 — Data Quality & Testing
### DE Training Programme | RetailCo Retail Data Warehouse

**Author:** Diluksha Perera  
**Date:** 2026-04-29  
**Challenge:** Build a Data Quality Framework for a PostgreSQL retail data warehouse

---

## Overview

This repository contains the complete Month 4 challenge submission for the Data Engineering training programme. The challenge required designing and implementing a production-grade data quality framework for the RetailCo retail data warehouse — a PostgreSQL gold layer with 5 dimension tables and 2 fact tables.

The framework covers all six DAMA DMBOK quality dimensions (Completeness, Accuracy, Consistency, Uniqueness, Validity, Timeliness) and was validated against a mirror database (`retaildw_dq`) containing eight deliberately injected defects to prove detection capability.

---

## Repository Structure

```
month4/
│
├── README.md                                   ← this file
│
├── ── Deliverables ──────────────────────────────────────────────────
├── diluksha-month4-quality-assessment.md       ← Deliverable 1: Quality assessment report
├── diluksha-month4-ge-suite.py                 ← Deliverable 2: GE expectation suites (all tables)
├── diluksha-month4-data-contracts.yaml         ← Deliverable 3: Data contract definitions
├── diluksha-month4-quality-dashboard.md        ← Deliverable 4: Quality metrics dashboard design
├── diluksha-month4-validation-report.md        ← Deliverable 5: Validation results & remediation
│
├── ── Great Expectations Project ────────────────────────────────────
├── gx/
│   ├── great_expectations.yml                  ← GX context configuration
│   ├── expectations/                           ← Saved expectation suites (JSON)
│   │   ├── dim_customer_suite.json             ← 28 expectations
│   │   ├── dim_product_suite.json              ← 21 expectations
│   │   ├── dim_store_suite.json                ← 20 expectations
│   │   ├── dim_date_suite.json                 ← 20 expectations
│   │   └── fact_sales_suite.json               ← 25 expectations
│   ├── validation_definitions/                 ← GX validation definition JSON files
│   └── uncommitted/
│       ├── config_variables.yml                ← DB credentials (gitignored)
│       ├── validations/                        ← Historical validation run results
│       └── data_docs/                          ← Generated HTML reports (gitignored)
│
├── ── Scripts ───────────────────────────────────────────────────────
├── scripts/
│   ├── 01_setup_gx_project.py                  ← Initialise GX context + datasource
│   ├── 02_test_connection.py                   ← Test PostgreSQL connectivity
│   ├── 03_build_dim_customer.py                ← Build + run dim_customer suite
│   ├── 03_build_dim_date.py                    ← Build + run dim_date suite
│   ├── 03_build_dim_product.py                 ← Build + run dim_product suite
│   ├── 03_build_dim_store.py                   ← Build + run dim_store suite
│   ├── 03_build_fact_sales.py                  ← Build + run fact_sales suite
│   ├── suites/                                 ← Suite builder modules (imported by 03_*.py)
│   │   ├── dim_customer_suite.py
│   │   ├── dim_product_suite.py
│   │   ├── dim_store_suite.py
│   │   ├── dim_date_suite.py
│   │   └── fact_sales_suite.py
│   ├── create_mirror_db.sql                    ← Creates retaildw_dq mirror schema
│   ├── inject_quality_issues.sql               ← Injects 8 synthetic defects (D1–D8)
│   ├── profile_tables.sql                      ← Column-level profiling queries
│   └── investigate_fact_sales_failures.sql     ← Deep-dive queries for fact_sales issues
│
└── requirements.txt                            ← Python dependencies
```

---

## Deliverables Summary

| # | File | Description |
|---|------|-------------|
| 1 | `diluksha-month4-quality-assessment.md` | Quality scorecard, issue catalogue (DQ-001–DQ-008), root cause analysis, maturity model, remediation priorities |
| 2 | `diluksha-month4-ge-suite.py` | 114 expectations across 5 tables; runnable end-to-end validation script |
| 3 | `diluksha-month4-data-contracts.yaml` | 6 YAML contracts (5 tables + RI policy) with field-level constraints, SLAs, PII tags, and changelog |
| 4 | `diluksha-month4-quality-dashboard.md` | 7-section dashboard design with backing SQL, 6 alert rules, KPI definitions, OpenMetadata integration |
| 5 | `diluksha-month4-validation-report.md` | Per-expectation PASS/FAIL tables, 8/8 defect detection, SQL remediation for all issues, Airflow integration plan |

---

## Quality Issues Documented

| Issue ID | Table | Dimension | Defect | Volume |
|----------|-------|-----------|--------|--------|
| DQ-001 | dim_customer | Completeness | NULL emails (opt-out migration bug) | 300 rows |
| DQ-002 | dim_customer | Uniqueness | Duplicate SCD2 current rows (race condition) | 10 customer_ids |
| DQ-003 | dim_customer | Validity | Email sentinel `'n/a'` not cleansed | 200 rows |
| DQ-004 | dim_customer | Validity | Segment typo `'Platnium'` instead of `'Premium'` | 50 rows |
| DQ-005 | dim_product | Validity | `list_price = 0` (promo import bug) | 15 rows |
| DQ-006 | dim_product | Accuracy | `cost_price >= list_price` (negative margin) | 10 rows |
| DQ-007 | fact_sales | Consistency | Orphan `customer_key` (FK not in dim_customer) | 50 rows |
| DQ-008 | fact_sales | Validity | `quantity = -1` (returns mixed into sales) | 100 rows |

**Detection rate: 8/8 (100%)** — every injected defect caught by the GE suite.

---

## Great Expectations Suite

### Expectation counts per table

| Table | Expectations | Predicted FAIL | Dimensions Covered |
|-------|:-----------:|:--------------:|-------------------|
| dim_customer | 32 | 4 | Completeness, Uniqueness, Validity, Consistency |
| dim_product | 24 | 2 | Completeness, Uniqueness, Validity, Accuracy |
| dim_store | 23 | 0 | Completeness, Uniqueness, Validity |
| dim_date | 23 | 0 | Completeness, Uniqueness, Validity, Consistency |
| fact_sales | 27 | 2 | Completeness, Uniqueness, Validity, Consistency, Accuracy |
| **Total** | **129** | **8** | All 6 DAMA dimensions |

### Key design decisions

- **`mostly` parameter** — `email NOT NULL` and email regex use `mostly=0.99` to allow the legitimate 1% opt-out null budget without false positives.
- **`UnexpectedRowsExpectation` for complex rules** — SCD2 current-row uniqueness, cross-table FK referential integrity, arithmetic accuracy (net_revenue, gross_profit), and format checks all use SQL-based row-level expectations rather than column-level expectations, which can't express joins or arithmetic.
- **`opening_date > CURRENT_DATE`** — dynamic SQL check (not a hardcoded year) so the guard remains valid regardless of calendar year.
- **Arithmetic tolerance `0.01`** — revenue and profit formula checks use a 1-cent tolerance to prevent false positives from float rounding during Decimal ↔ PostgreSQL numeric conversion.

---

## Setup & Running

### Prerequisites

- Python 3.9+
- PostgreSQL with `retaildw` (production) and `retaildw_dq` (mirror) databases
- The `retaildw_dq` mirror must be set up before running validations

### 1. Install dependencies

```bash
cd C:\de-training\month4
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2. Create the mirror database

Run in DBeaver or psql against the `retaildw_dq` connection:

```bash
psql -U dataeng -d retaildw_dq -f scripts/create_mirror_db.sql
```

### 3. Inject synthetic defects (for validation testing)

```bash
psql -U dataeng -d retaildw_dq -f scripts/inject_quality_issues.sql
```

This injects defects D1–D8 into the mirror, leaving `retaildw` (production) untouched.

### 4. Run the full validation suite (all 5 tables)

```bash
python diluksha-month4-ge-suite.py
```

### 5. Run a single table

```bash
python diluksha-month4-ge-suite.py --table dim_customer
python diluksha-month4-ge-suite.py --table fact_sales
```

### 6. Run individual build scripts (original modular approach)

```bash
python scripts/03_build_dim_customer.py
python scripts/03_build_fact_sales.py
# etc.
```

### 7. View the HTML Data Docs report

After any validation run:

```
gx\uncommitted\data_docs\local_site\index.html
```

Open in a browser for the full interactive report with per-expectation results, unexpected row samples, and run history.

---

## Connection Configuration

Database credentials are stored in `gx/uncommitted/config_variables.yml` (gitignored). The expected format is:

```yaml
retaildw_dq_connection_string: postgresql+psycopg2://dataeng:dataeng123@localhost:5432/retaildw_dq
```

To use a different host or credentials, update this file or set the environment variable:

```bash
export GX_RETAILDW_DQ_CONN="postgresql+psycopg2://user:pass@host:5432/retaildw_dq"
```

---

## Validation Results (against retaildw_dq with injected defects)

| Table | Total | PASS | FAIL | Pass Rate |
|-------|------:|-----:|-----:|----------:|
| dim_date | 20 | 20 | 0 | 100.0% |
| dim_store | 20 | 20 | 0 | 100.0% |
| dim_product | 21 | 19 | 2 | 90.5% |
| dim_customer | 28 | 24 | 4 | 85.7% |
| fact_sales | 25 | 23 | 2 | 92.0% |
| **Total** | **114** | **106** | **8** | **93.0%** |

All 8 failures are intentional — each maps to a deliberately injected defect and is flagged `"predicted": "FAIL"` in the suite metadata.

---

## Data Contracts

Contracts follow [Data Contract Specification v0.9.3](https://datacontract.com/) and cover:

- Field-level type, nullability, range, enum, regex, and formula constraints
- Cross-table referential integrity policy (separate document)
- SLAs: availability, freshness, completeness, accuracy, and volume
- PII classification (`email`, `customer_name`)
- Anomaly detection rules on `fact_sales` (volume, freshness, revenue spike)
- Versioned changelogs on all contracts

---

## Anomaly Detection

Three detection strategies are implemented in the validation report and dashboard:

| Strategy | Method | Threshold | Target |
|----------|--------|-----------|--------|
| Volume — partial load | 7-day rolling average | `< rolling_7d_avg * 0.5` | fact_sales daily count |
| Statistical anomaly | z-score (30-day baseline) | `\|z\| > 3` (3-sigma) | fact_sales daily count |
| Revenue spike | z-score (30-day baseline) | `\|z\| > 3` | daily total revenue |
| Freshness SLA | Time elapsed since load | `> 24 hours` | all daily tables |

---

## Offline Milestones (Before Month 5)

- [ ] Complete Great Expectations official tutorial
- [ ] Add 20+ expectations to each table's suite (already done in deliverable)
- [ ] Implement cross-table referential integrity checks in Airflow DAG
- [ ] Integrate `diluksha-month4-ge-suite.py` into an Airflow DAG for automated validation
- [ ] Read *Data Quality Fundamentals* by Barr Moses et al.
- [ ] Design a formal data quality SLA document for one data product

---

## Resources

| Resource | Link |
|----------|------|
| Great Expectations Docs | https://docs.greatexpectations.io/ |
| Data Contract Specification | https://datacontract.com/ |
| OpenMetadata Docs | https://docs.open-metadata.org/ |
| DAMA DMBOK Quality Dimensions | https://www.dama.org/cpages/body-of-knowledge |
| GX Expectation Gallery | https://greatexpectations.io/expectations/ |

---

## .gitignore Recommendations

```gitignore
# Python
venv/
__pycache__/
*.pyc

# GX secrets and generated output
gx/uncommitted/config_variables.yml
gx/uncommitted/data_docs/

# IDE
.vscode/
.idea/
```

---

*Month 4 — Data Quality & Testing | DE Training Programme*
