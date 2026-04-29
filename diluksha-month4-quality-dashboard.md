# Data Quality Metrics Dashboard Design
## RetailCo Retail Data Warehouse — Month 4

**Author:** Diluksha Perera  
**Date:** 2026-04-29  
**Tool:** Grafana (recommended) / Metabase / Custom HTML  
**Refresh:** Every 6 hours (aligned with ETL window)

---

## 1. Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Data Source: quality_metrics schema (PostgreSQL) + GX validation JSON   │
│  Scheduler:   Apache Airflow — quality_check DAG (06:30 UTC daily)       │
│  Alerts:      PagerDuty (critical) → Slack (high) → Email (medium/low)   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Metrics Storage DDL

```sql
-- Schema to persist all validation run results for trending
CREATE TABLE quality_metrics.validation_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    run_timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    table_name      VARCHAR(50) NOT NULL,
    dimension       VARCHAR(20) NOT NULL,   -- Completeness, Accuracy, etc.
    metric_name     VARCHAR(100) NOT NULL,
    metric_value    DECIMAL(8,4) NOT NULL,  -- Score 0.0–1.0
    pass_count      INTEGER NOT NULL,
    fail_count      INTEGER NOT NULL,
    total_count     INTEGER NOT NULL,
    status          VARCHAR(10) NOT NULL,   -- PASS / FAIL
    issue_ids       TEXT[],                 -- e.g. {DQ-001, DQ-002}
    load_date       DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Index for time-series queries
CREATE INDEX idx_vr_table_ts ON quality_metrics.validation_runs (table_name, run_timestamp DESC);

-- Summary view (used by all dashboard panels)
CREATE VIEW quality_metrics.daily_scores AS
SELECT
    load_date,
    table_name,
    dimension,
    AVG(metric_value)                               AS avg_score,
    SUM(pass_count)                                 AS total_pass,
    SUM(fail_count)                                 AS total_fail,
    CASE WHEN SUM(fail_count) = 0 THEN 'PASS' ELSE 'FAIL' END AS overall_status
FROM quality_metrics.validation_runs
GROUP BY load_date, table_name, dimension;
```

---

## 2. Dashboard Layout

### Section 1 — Overall Quality Score (Top Bar)

```
╔══════════════════════════════════════════════════════════════════════╗
║  OVERALL DATA QUALITY SCORE           Target: 99.5%                 ║
║                                                                      ║
║  ┌──────────┐  97.4%  [██████████████████████░░] ← gap to target    ║
║  │  97.4%   │                                                        ║
║  │  ⚠ BELOW │  Completeness:  99.4%  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░]       ║
║  │  TARGET  │  Accuracy:      99.7%  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]  ✅   ║
║  └──────────┘  Consistency:   99.7%  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]  ✅   ║
║                Uniqueness:    99.98% [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]  ⚠️   ║
║                Validity:      98.8%  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░]  ❌   ║
║                Timeliness:    97.5%  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░]  ❌   ║
║                                                                      ║
║  Last run: 2026-04-29 06:32 UTC  │  Next run: 2026-04-30 06:30 UTC  ║
╚══════════════════════════════════════════════════════════════════════╝
```

**KPIs in this section:**

| KPI | Query | Alert threshold |
|-----|-------|----------------|
| Overall score | `AVG(metric_value)` across all dimensions | < 95% → Critical |
| Dimension scores | `AVG(metric_value)` GROUP BY dimension | < 99.5% → Warning |
| Time since last run | `NOW() - MAX(run_timestamp)` | > 25h → Critical |

---

### Section 2 — Quality Score by Table (Table Scorecard)

```
╔══════════════════════════════════════════════════════════════════════╗
║  TABLE QUALITY SCORES — Last 24 Hours                               ║
║                                                                      ║
║  Table          Complete  Accurate  Consistent  Unique  Valid  Score ║
║  ─────────────────────────────────────────────────────────────────── ║
║  dim_date       100.0%   100.0%    100.0%      100.0%  100.0% 100%  ║
║  dim_store       100.0%  100.0%    100.0%      100.0%  100.0%  99.7%║
║  dim_product    100.0%   98.5%     100.0%      100.0%  97.5%   99.0%║
║  dim_customer    97.0%   100.0%     98.5%       99.9%  97.5%   98.5%║
║  fact_sales     100.0%   99.8%      99.99%     100.0%  99.98%  99.3%║
╚══════════════════════════════════════════════════════════════════════╝
```

**Backing SQL:**

```sql
SELECT
    table_name,
    MAX(CASE WHEN dimension = 'Completeness' THEN avg_score END)   AS completeness,
    MAX(CASE WHEN dimension = 'Accuracy'     THEN avg_score END)   AS accuracy,
    MAX(CASE WHEN dimension = 'Consistency'  THEN avg_score END)   AS consistency,
    MAX(CASE WHEN dimension = 'Uniqueness'   THEN avg_score END)   AS uniqueness,
    MAX(CASE WHEN dimension = 'Validity'     THEN avg_score END)   AS validity,
    AVG(avg_score)                                                  AS overall_score
FROM quality_metrics.daily_scores
WHERE load_date = CURRENT_DATE
GROUP BY table_name
ORDER BY overall_score;
```

---

### Section 3 — 30-Day Quality Trend (Time Series)

```
╔══════════════════════════════════════════════════════════════════════╗
║  30-DAY OVERALL QUALITY TREND                                        ║
║                                                                      ║
║ 100% ┤                                          ╭───╮               ║
║  99% ┤                            ╭────╮       ╯   ╰───            ║
║  98% ┤            ╭───╮          ╯    ╰───────╯                    ║
║  97% ┤───────────╯   ╰──────────╯                                   ║
║      ├────┬────┬────┬────┬────┬────┬────┬────┬────┬────            ║
║       Apr1  5   9  13  17  21  25  29  May3   7                    ║
║                                                                      ║
║  — Overall   — Validity   — Consistency   ─── Target (99.5%)        ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Backing SQL:**

```sql
SELECT
    load_date,
    AVG(avg_score) FILTER (WHERE TRUE)                             AS overall,
    AVG(avg_score) FILTER (WHERE dimension = 'Validity')           AS validity,
    AVG(avg_score) FILTER (WHERE dimension = 'Consistency')        AS consistency,
    0.995                                                           AS target_line
FROM quality_metrics.daily_scores
WHERE load_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY load_date
ORDER BY load_date;
```

**Trend interpretation rules:**

- A score **declining for 3 consecutive days** triggers a Warning alert regardless of absolute level.
- A score **below target for 7 consecutive days** escalates to a P1 incident.
- A sudden **drop > 2% in a single day** triggers immediate Slack notification.

---

### Section 4 — Active Quality Issues (Issue Tracker)

```
╔══════════════════════════════════════════════════════════════════════╗
║  ACTIVE QUALITY ISSUES                          As of: 2026-04-29   ║
║                                                                      ║
║  Severity  │ Count │ Issue IDs                                       ║
║  ──────────┼───────┼──────────────────────────────────────────────  ║
║  CRITICAL  │   2   │ DQ-002 (SCD2 dupe), DQ-007 (orphan FK)         ║
║  HIGH      │   3   │ DQ-001 (null email), DQ-005 (zero price),       ║
║            │       │ DQ-008 (neg qty)                                ║
║  MEDIUM    │   2   │ DQ-004 (segment typo), DQ-006 (cost>price)      ║
║  LOW       │   1   │ DQ-003 ('n/a' email sentinel)                   ║
║  ──────────┼───────┼──────────────────────────────────────────────  ║
║  TOTAL     │   8   │                                                 ║
║                                                                      ║
║  [View Remediation Plan →]    [Export to Jira →]                    ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Backing SQL:**

```sql
SELECT
    severity,
    COUNT(*)         AS issue_count,
    ARRAY_AGG(issue_id ORDER BY issue_id) AS issue_ids
FROM quality_metrics.active_issues
WHERE resolved_date IS NULL
GROUP BY severity
ORDER BY CASE severity
    WHEN 'CRITICAL' THEN 1
    WHEN 'HIGH'     THEN 2
    WHEN 'MEDIUM'   THEN 3
    WHEN 'LOW'      THEN 4
END;
```

---

### Section 5 — Referential Integrity Monitor

```
╔══════════════════════════════════════════════════════════════════════╗
║  REFERENTIAL INTEGRITY — fact_sales                                  ║
║                                                                      ║
║  FK Check                  │ Orphan Count │ Status                   ║
║  ──────────────────────────┼─────────────┼─────────────────────     ║
║  → dim_customer            │     50       │ ❌ FAIL (DQ-007)         ║
║  → dim_product             │      0       │ ✅ PASS                  ║
║  → dim_store               │      0       │ ✅ PASS                  ║
║  → dim_date                │      0       │ ✅ PASS                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Backing SQL (runs on each ETL completion):**

```sql
-- Stored in quality_metrics.referential_integrity_checks
SELECT
    check_name,
    orphan_count,
    CASE WHEN orphan_count = 0 THEN 'PASS' ELSE 'FAIL' END AS status,
    check_timestamp
FROM quality_metrics.referential_integrity_checks
WHERE check_timestamp = (SELECT MAX(check_timestamp)
                         FROM quality_metrics.referential_integrity_checks);
```

---

### Section 6 — Timeliness Monitor

```
╔══════════════════════════════════════════════════════════════════════╗
║  TIMELINESS / SLA MONITOR                                            ║
║                                                                      ║
║  Table          SLA Target   Last Load       Delay   Status         ║
║  ─────────────────────────────────────────────────────────────────  ║
║  fact_sales     06:00 UTC    2026-04-29 05:48  -12m   ✅ On time    ║
║  dim_customer   06:00 UTC    2026-04-29 05:52   -8m   ✅ On time    ║
║  dim_product    06:00 UTC    2026-04-29 05:55   -5m   ✅ On time    ║
║  dim_store      Weekly Mon   2026-04-27 04:00   0h    ✅ On time    ║
║  dim_date       Annual       2025-12-31 00:00   0d    ✅ On time    ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

### Section 7 — Volume Anomaly Detection

```
╔══════════════════════════════════════════════════════════════════════╗
║  FACT_SALES DAILY VOLUME — 14 Day Rolling                           ║
║                                                                      ║
║       120K ┤                        ●                               ║
║       100K ┤    ●     ●     ●          ●     ●                      ║
║        80K ┤        ●    ●    ●   ●       ●     ●  ←today           ║
║        60K ┤─────────────────────────────────────────               ║
║        40K ┤   [Lower bound: 50% of 7-day avg = 42K]               ║
║       ──────┼──────────────────────────────────────                 ║
║              Apr16 17 18 19 20 21 22 23 24 25 26 27 28 29          ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Statistical anomaly detection logic:**

```sql
WITH daily_volumes AS (
    SELECT
        load_date,
        COUNT(*) AS row_count
    FROM warehouse.fact_sales
    GROUP BY load_date
),
rolling_stats AS (
    SELECT
        load_date,
        row_count,
        AVG(row_count) OVER (
            ORDER BY load_date
            ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
        ) AS rolling_7d_avg,
        STDDEV(row_count) OVER (
            ORDER BY load_date
            ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING
        ) AS rolling_30d_stddev
    FROM daily_volumes
)
SELECT
    load_date,
    row_count,
    rolling_7d_avg,
    ROUND(rolling_7d_avg * 0.5, 0)  AS lower_bound_50pct,
    ROUND(rolling_7d_avg * 1.5, 0)  AS upper_bound_50pct,
    CASE
        WHEN row_count < rolling_7d_avg * 0.5 THEN 'LOW_VOLUME_ALERT'
        WHEN row_count > rolling_7d_avg * 1.5 THEN 'HIGH_VOLUME_ALERT'
        ELSE 'NORMAL'
    END AS volume_status,
    -- Z-score based detection (catches subtler shifts)
    ROUND((row_count - rolling_7d_avg) / NULLIF(rolling_30d_stddev, 0), 2) AS z_score
FROM rolling_stats
ORDER BY load_date DESC;
```

**Alert rule:** Fire `HIGH_VOLUME_ALERT` if `|z_score| > 3` (3-sigma rule) OR if count falls below 50% of 7-day rolling average.

---

## 3. Alert Configuration

```yaml
# alerting/quality_alerts.yaml
alerts:

  - id: ALT-001
    name: critical_quality_score_failure
    condition: overall_quality_score < 0.95
    severity: critical
    description: >
      Overall warehouse quality dropped below 95%.
      Likely indicates a systemic ETL failure or schema change.
    channels:
      - pagerduty
      - slack:#data-incidents
    recipients:
      - data-engineering-team
      - data-platform-lead
    runbook: https://wiki.retailco.internal/dq/runbooks/critical-quality-failure
    cooldown_minutes: 60

  - id: ALT-002
    name: referential_integrity_break
    condition: orphan_record_count > 0
    severity: critical
    description: >
      Orphan FK rows detected in fact_sales.
      Revenue cannot be attributed; reports will show discrepancies.
    channels:
      - pagerduty
      - slack:#data-incidents
    recipients:
      - data-engineering-team
    runbook: https://wiki.retailco.internal/dq/runbooks/referential-integrity
    cooldown_minutes: 0   # Alert on EVERY occurrence; no cooldown

  - id: ALT-003
    name: freshness_sla_breach
    condition: data_age_hours > 24
    severity: high
    description: Daily ETL has not landed within the 24-hour SLA window.
    channels:
      - slack:#data-engineering
      - email
    recipients:
      - data-engineering-team
    cooldown_minutes: 120

  - id: ALT-004
    name: volume_anomaly_low
    condition: daily_row_count < rolling_7d_avg * 0.5
    severity: high
    description: >
      fact_sales daily load is less than 50% of the 7-day rolling average.
      Possible partial load or upstream data loss.
    channels:
      - slack:#data-engineering
    recipients:
      - data-engineering-team
    cooldown_minutes: 60

  - id: ALT-005
    name: quality_trend_declining
    condition: score_3day_trend < -0.01
    severity: medium
    description: Overall quality score has declined more than 1% over 3 consecutive days.
    channels:
      - slack:#data-engineering
    recipients:
      - data-engineering-team
    cooldown_minutes: 1440   # Once per day maximum

  - id: ALT-006
    name: scd2_duplicate_current_rows
    condition: scd2_duplicate_count > 0
    severity: critical
    description: >
      More than one is_current=TRUE row per customer_id detected.
      Customer analytics will double-count affected customers.
    channels:
      - pagerduty
      - slack:#data-incidents
    recipients:
      - data-engineering-team
    cooldown_minutes: 0
```

---

## 4. Quality KPI Definitions

| KPI | Formula | Target | Owner |
|-----|---------|--------|-------|
| Overall Quality Score | `AVG(dimension_score)` across all tables and dimensions | ≥ 99.5% | Data Engineering |
| Completeness Score | `(non-null required field values) / (total required field values)` | 100% | Data Engineering |
| Accuracy Score | `(rows passing arithmetic checks) / total rows` | ≥ 99.5% | Data Engineering |
| Consistency Score | `(rows with valid FK references) / total rows` | 100% | Data Engineering |
| Uniqueness Score | `(distinct PKs) / total rows` for each table | 100% | Data Engineering |
| Validity Score | `(rows passing all format/range/enum checks) / total rows` | ≥ 99.5% | Data Engineering |
| Timeliness Score | `(loads arriving before SLA deadline) / (total expected loads)` | ≥ 99.5% | Data Ops |
| Mean Time to Detect (MTTD) | `AVG(alert_time - defect_injection_time)` | ≤ 6h | Data Engineering |
| Mean Time to Resolve (MTTR) | `AVG(resolved_time - alert_time)` | ≤ 48h | Data Engineering |
| Open Critical Issues | `COUNT(active_issues WHERE severity = 'CRITICAL')` | 0 | Data Engineering |
| SLA Breach Rate | `(SLA breaches per month) / (expected loads per month)` | ≤ 0.5% | Data Ops |

---

## 5. OpenMetadata Integration Notes

OpenMetadata complements this dashboard by providing:

1. **Column-level PII classification** — tag `email`, `customer_name` as PII; integrated with access control.
2. **Data lineage** — visualise bronze → silver → gold flows; quickly trace a quality issue to its source.
3. **Profiler statistics** — column null rates, distinct counts, histograms persisted and trended automatically.
4. **Quality test mapping** — link GX expectations to OpenMetadata test definitions for a unified quality view.
5. **Glossary** — define `net_revenue`, `gross_profit`, `customer_segment` with business definitions so stakeholders use the same terms as the quality rules.

**Docker quick-start:**
```bash
# From https://docs.open-metadata.org/quick-start/local-docker-deployment
git clone https://github.com/open-metadata/OpenMetadata.git
cd OpenMetadata/docker/local-metadata
docker compose up -d
# Access at http://localhost:8585
```

---

## 6. Dashboard Refresh Schedule

| Panel | Refresh Frequency | Trigger |
|-------|------------------|---------|
| Overall Quality Score | After each ETL run (~06:30 UTC) | Airflow callback |
| Table Scorecard | After each ETL run | Airflow callback |
| 30-Day Trend | Once daily at 07:00 UTC | Scheduled |
| Active Issues | Real-time | Alert webhook |
| Referential Integrity | After each ETL run | Airflow callback |
| Timeliness Monitor | Hourly | Scheduled |
| Volume Anomaly | After each ETL run | Airflow callback |

---

*Dashboard design for Month 4 Data Engineering Training — RetailCo Retail Data Warehouse.*
