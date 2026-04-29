-- ============================================================
-- Month 4 - Data Quality Profiling
-- Target: retaildw.warehouse (5 tables)
-- Connection: dataeng@localhost:5432/retaildw
-- Author: Diluksha Perera
-- Purpose: Profile all 5 warehouse tables to identify quality
--          issues BEFORE writing Great Expectations suites.
-- Run in: DBeaver (SQL Editor on retaildw connection)
-- ============================================================


-- ============================================================
-- SECTION 0: Schema inventory (already run)
-- ============================================================
-- See completed output stored separately.


-- ============================================================
-- SECTION 1: dim_customer profiling
-- ============================================================

-- 1.1 Eyeball sample - 10 rows, ALL columns
SELECT * FROM warehouse.dim_customer LIMIT 10;

-- 1.2 Row count and SCD2 shape
SELECT
    COUNT(*)                                            AS total_rows,
    COUNT(DISTINCT customer_key)                        AS distinct_customer_keys,
    COUNT(DISTINCT customer_id)                         AS distinct_customer_ids,
    COUNT(DISTINCT customer_id || '|' || effective_date::text) AS distinct_scd2_keys,
    SUM(CASE WHEN is_current THEN 1 ELSE 0 END)         AS current_rows,
    SUM(CASE WHEN NOT is_current THEN 1 ELSE 0 END)     AS historical_rows
FROM warehouse.dim_customer;

-- 1.3 NULL analysis per column
SELECT
    COUNT(*)                                         AS total_rows,
    COUNT(*) - COUNT(customer_key)                   AS null_customer_key,
    COUNT(*) - COUNT(customer_id)                    AS null_customer_id,
    COUNT(*) - COUNT(customer_name)                  AS null_customer_name,
    COUNT(*) - COUNT(email)                          AS null_email,
    COUNT(*) - COUNT(city)                           AS null_city,
    COUNT(*) - COUNT(state)                          AS null_state,
    COUNT(*) - COUNT(zip_code)                       AS null_zip_code,
    COUNT(*) - COUNT(customer_segment)               AS null_customer_segment,
    COUNT(*) - COUNT(effective_date)                 AS null_effective_date,
    COUNT(*) - COUNT(expiry_date)                    AS null_expiry_date,
    COUNT(*) - COUNT(is_current)                     AS null_is_current
FROM warehouse.dim_customer;

-- 1.4 customer_segment value distribution (catches typos, unknowns)
SELECT
    customer_segment,
    COUNT(*) AS row_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM warehouse.dim_customer
GROUP BY customer_segment
ORDER BY row_count DESC;

-- 1.5 Email validity - how many rows have malformed email?
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END)                       AS null_email,
    SUM(CASE WHEN email = '' THEN 1 ELSE 0 END)                          AS empty_email,
    SUM(CASE WHEN email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN 1 ELSE 0 END) AS valid_email_format,
    SUM(CASE WHEN email IS NOT NULL AND email <> '' AND email !~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN 1 ELSE 0 END) AS invalid_email_format
FROM warehouse.dim_customer;

-- 1.6 Duplicate customer_id with is_current = TRUE (SCD2 integrity)
-- Should return 0 rows in a correctly-maintained SCD2
SELECT
    customer_id,
    COUNT(*) AS current_duplicate_count
FROM warehouse.dim_customer
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- 1.7 Date range sanity (future effective_date = data bug)
SELECT
    MIN(effective_date) AS earliest_effective,
    MAX(effective_date) AS latest_effective,
    MIN(expiry_date)    AS earliest_expiry,
    MAX(expiry_date)    AS latest_expiry,
    SUM(CASE WHEN effective_date > CURRENT_DATE THEN 1 ELSE 0 END) AS future_effective_count,
    SUM(CASE WHEN expiry_date < effective_date THEN 1 ELSE 0 END) AS expiry_before_effective
FROM warehouse.dim_customer;


-- ============================================================
-- SECTION 2: dim_product profiling
-- ============================================================

-- 2.1 Eyeball sample
SELECT * FROM warehouse.dim_product LIMIT 10;

-- 2.2 Row count and uniqueness
SELECT
    COUNT(*)                        AS total_rows,
    COUNT(DISTINCT product_key)     AS distinct_product_keys,
    COUNT(DISTINCT product_id)      AS distinct_product_ids
FROM warehouse.dim_product;

-- 2.3 NULL analysis
SELECT
    COUNT(*)                                 AS total_rows,
    COUNT(*) - COUNT(product_key)            AS null_product_key,
    COUNT(*) - COUNT(product_id)             AS null_product_id,
    COUNT(*) - COUNT(product_name)           AS null_product_name,
    COUNT(*) - COUNT(category)               AS null_category,
    COUNT(*) - COUNT(subcategory)            AS null_subcategory,
    COUNT(*) - COUNT(brand)                  AS null_brand,
    COUNT(*) - COUNT(list_price)             AS null_list_price,
    COUNT(*) - COUNT(cost_price)             AS null_cost_price
FROM warehouse.dim_product;

-- 2.4 Category value distribution
SELECT
    category,
    COUNT(*) AS row_count
FROM warehouse.dim_product
GROUP BY category
ORDER BY row_count DESC;

-- 2.5 Price validity checks
SELECT
    COUNT(*)                                               AS total_rows,
    SUM(CASE WHEN list_price <= 0 THEN 1 ELSE 0 END)       AS list_price_zero_or_negative,
    SUM(CASE WHEN cost_price <= 0 THEN 1 ELSE 0 END)       AS cost_price_zero_or_negative,
    SUM(CASE WHEN cost_price > list_price THEN 1 ELSE 0 END) AS cost_exceeds_list,
    MIN(list_price)                                        AS min_list_price,
    MAX(list_price)                                        AS max_list_price,
    MIN(cost_price)                                        AS min_cost_price,
    MAX(cost_price)                                        AS max_cost_price,
    ROUND(AVG(list_price), 2)                              AS avg_list_price,
    ROUND(AVG(cost_price), 2)                              AS avg_cost_price
FROM warehouse.dim_product;


-- ============================================================
-- SECTION 3: dim_store profiling
-- ============================================================

-- 3.1 Eyeball sample
SELECT * FROM warehouse.dim_store LIMIT 10;

-- 3.2 Row count and uniqueness
SELECT
    COUNT(*)                       AS total_rows,
    COUNT(DISTINCT store_key)      AS distinct_store_keys,
    COUNT(DISTINCT store_id)       AS distinct_store_ids
FROM warehouse.dim_store;

-- 3.3 NULL analysis
SELECT
    COUNT(*)                              AS total_rows,
    COUNT(*) - COUNT(store_key)           AS null_store_key,
    COUNT(*) - COUNT(store_id)            AS null_store_id,
    COUNT(*) - COUNT(store_name)          AS null_store_name,
    COUNT(*) - COUNT(city)                AS null_city,
    COUNT(*) - COUNT(state)               AS null_state,
    COUNT(*) - COUNT(region)              AS null_region,
    COUNT(*) - COUNT(store_type)          AS null_store_type,
    COUNT(*) - COUNT(opening_date)        AS null_opening_date
FROM warehouse.dim_store;

-- 3.4 store_type and region distributions
SELECT store_type, COUNT(*) AS row_count
FROM warehouse.dim_store
GROUP BY store_type
ORDER BY row_count DESC;

SELECT region, COUNT(*) AS row_count
FROM warehouse.dim_store
GROUP BY region
ORDER BY row_count DESC;

-- 3.5 opening_date validity (future dates = data entry error)
SELECT
    MIN(opening_date) AS earliest_opening,
    MAX(opening_date) AS latest_opening,
    SUM(CASE WHEN opening_date > CURRENT_DATE THEN 1 ELSE 0 END) AS future_opening_count,
    CURRENT_DATE      AS today
FROM warehouse.dim_store;

-- 3.6 state code length validity (should always be 2 chars)
SELECT
    LENGTH(state) AS state_length,
    COUNT(*)      AS row_count
FROM warehouse.dim_store
GROUP BY LENGTH(state)
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 4: dim_date profiling
-- ============================================================

-- 4.1 Eyeball sample
SELECT * FROM warehouse.dim_date LIMIT 10;

-- 4.2 Date range coverage
SELECT
    COUNT(*)                          AS total_rows,
    COUNT(DISTINCT date_key)          AS distinct_date_keys,
    COUNT(DISTINCT full_date)         AS distinct_dates,
    MIN(full_date)                    AS earliest_date,
    MAX(full_date)                    AS latest_date,
    MAX(full_date) - MIN(full_date)   AS day_span
FROM warehouse.dim_date;

-- 4.3 Validity checks - numeric fields in correct ranges
SELECT
    SUM(CASE WHEN month_number NOT BETWEEN 1 AND 12 THEN 1 ELSE 0 END)  AS invalid_month,
    SUM(CASE WHEN quarter_number NOT BETWEEN 1 AND 4 THEN 1 ELSE 0 END) AS invalid_quarter,
    SUM(CASE WHEN day_of_week NOT BETWEEN 1 AND 7 THEN 1 ELSE 0 END)    AS invalid_day_of_week,
    COUNT(DISTINCT year_number)                                         AS distinct_years,
    MIN(year_number)                                                    AS min_year,
    MAX(year_number)                                                    AS max_year
FROM warehouse.dim_date;

-- 4.4 date_key format (expected YYYYMMDD integer)
SELECT
    MIN(date_key) AS min_date_key,
    MAX(date_key) AS max_date_key,
    SUM(CASE WHEN date_key < 19000101 OR date_key > 21001231 THEN 1 ELSE 0 END) AS date_key_out_of_range
FROM warehouse.dim_date;


-- ============================================================
-- SECTION 5: fact_sales profiling
-- ============================================================

-- 5.1 Eyeball sample
SELECT * FROM warehouse.fact_sales LIMIT 10;

-- 5.2 Row count and uniqueness
SELECT
    COUNT(*)                                       AS total_rows,
    COUNT(DISTINCT sales_key)                      AS distinct_sales_keys,
    COUNT(DISTINCT order_id || '|' || order_line_num::text) AS distinct_order_lines
FROM warehouse.fact_sales;

-- 5.3 Duplicate (order_id, order_line_num) check
SELECT order_id, order_line_num, COUNT(*) AS dup_count
FROM warehouse.fact_sales
GROUP BY order_id, order_line_num
HAVING COUNT(*) > 1
LIMIT 20;

-- 5.4 NULL analysis (schema says NOT NULL but let's verify)
SELECT
    COUNT(*)                              AS total_rows,
    COUNT(*) - COUNT(sales_key)           AS null_sales_key,
    COUNT(*) - COUNT(date_key)            AS null_date_key,
    COUNT(*) - COUNT(customer_key)        AS null_customer_key,
    COUNT(*) - COUNT(product_key)         AS null_product_key,
    COUNT(*) - COUNT(store_key)           AS null_store_key,
    COUNT(*) - COUNT(order_id)            AS null_order_id,
    COUNT(*) - COUNT(quantity)            AS null_quantity,
    COUNT(*) - COUNT(unit_price)          AS null_unit_price,
    COUNT(*) - COUNT(unit_cost)           AS null_unit_cost,
    COUNT(*) - COUNT(discount_amount)     AS null_discount,
    COUNT(*) - COUNT(net_revenue)         AS null_net_revenue,
    COUNT(*) - COUNT(gross_profit)        AS null_gross_profit,
    COUNT(*) - COUNT(tax_amount)          AS null_tax_amount
FROM warehouse.fact_sales;

-- 5.5 Measure validity checks
SELECT
    COUNT(*)                                                      AS total_rows,
    SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END)                AS qty_zero_or_neg,
    SUM(CASE WHEN quantity > 10000 THEN 1 ELSE 0 END)             AS qty_above_10000,
    SUM(CASE WHEN unit_price <= 0 THEN 1 ELSE 0 END)              AS price_zero_or_neg,
    SUM(CASE WHEN unit_cost < 0 THEN 1 ELSE 0 END)                AS cost_negative,
    SUM(CASE WHEN discount_amount < 0 THEN 1 ELSE 0 END)          AS discount_negative,
    SUM(CASE WHEN net_revenue < 0 THEN 1 ELSE 0 END)              AS revenue_negative,
    MIN(quantity)                                                 AS min_qty,
    MAX(quantity)                                                 AS max_qty,
    MIN(unit_price)                                               AS min_price,
    MAX(unit_price)                                               AS max_price,
    MIN(net_revenue)                                              AS min_revenue,
    MAX(net_revenue)                                              AS max_revenue
FROM warehouse.fact_sales;

-- 5.6 Revenue arithmetic consistency
-- net_revenue should equal (quantity * unit_price) - discount_amount (within rounding)
SELECT
    COUNT(*)                                                                              AS total_rows,
    SUM(CASE
        WHEN ABS(net_revenue - (quantity * unit_price - discount_amount)) > 0.01
        THEN 1 ELSE 0 END)                                                                AS revenue_inconsistent,
    SUM(CASE
        WHEN ABS(gross_profit - (net_revenue - (quantity * unit_cost))) > 0.01
        THEN 1 ELSE 0 END)                                                                AS gross_profit_inconsistent
FROM warehouse.fact_sales;


-- ============================================================
-- SECTION 6: Cross-table referential integrity
-- ============================================================

-- 6.1 fact_sales -> dim_customer (orphan customer_keys)
SELECT
    'fact_sales -> dim_customer' AS check_name,
    COUNT(*)                     AS orphan_count,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM warehouse.fact_sales f
LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key
WHERE c.customer_key IS NULL;

-- 6.2 fact_sales -> dim_product
SELECT
    'fact_sales -> dim_product' AS check_name,
    COUNT(*)                    AS orphan_count,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM warehouse.fact_sales f
LEFT JOIN warehouse.dim_product p ON f.product_key = p.product_key
WHERE p.product_key IS NULL;

-- 6.3 fact_sales -> dim_store
SELECT
    'fact_sales -> dim_store' AS check_name,
    COUNT(*)                  AS orphan_count,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM warehouse.fact_sales f
LEFT JOIN warehouse.dim_store s ON f.store_key = s.store_key
WHERE s.store_key IS NULL;

-- 6.4 fact_sales -> dim_date
SELECT
    'fact_sales -> dim_date' AS check_name,
    COUNT(*)                 AS orphan_count,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM warehouse.fact_sales f
LEFT JOIN warehouse.dim_date d ON f.date_key = d.date_key
WHERE d.date_key IS NULL;


-- ============================================================
-- SECTION 7: Cross-table summary - single scorecard row
-- ============================================================

WITH fact_counts AS (
    SELECT
        COUNT(*) AS fact_rows,
        SUM(CASE WHEN c.customer_key IS NULL THEN 1 ELSE 0 END) AS orphan_customer,
        SUM(CASE WHEN p.product_key IS NULL THEN 1 ELSE 0 END) AS orphan_product,
        SUM(CASE WHEN s.store_key IS NULL THEN 1 ELSE 0 END) AS orphan_store,
        SUM(CASE WHEN d.date_key IS NULL THEN 1 ELSE 0 END) AS orphan_date,
        SUM(CASE
            WHEN ABS(net_revenue - (quantity * unit_price - discount_amount)) > 0.01
            THEN 1 ELSE 0 END) AS revenue_broken
    FROM warehouse.fact_sales f
    LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key
    LEFT JOIN warehouse.dim_product p ON f.product_key = p.product_key
    LEFT JOIN warehouse.dim_store s ON f.store_key = s.store_key
    LEFT JOIN warehouse.dim_date d ON f.date_key = d.date_key
)
SELECT
    fact_rows,
    orphan_customer,
    orphan_product,
    orphan_store,
    orphan_date,
    revenue_broken,
    ROUND(100.0 * (fact_rows - orphan_customer - orphan_product - orphan_store - orphan_date - revenue_broken) / NULLIF(fact_rows, 0), 2) AS clean_pct
FROM fact_counts;