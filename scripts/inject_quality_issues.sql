-- ============================================================
-- Month 4 — Quality Defect Injection
-- Target: retaildw_dq.warehouse (MIRROR ONLY — never retaildw)
-- Purpose: Introduce synthetic defects matching the challenge
--          file's "Quality Issues Discovered" catalogue so the
--          Great Expectations suite has real issues to detect.
--
-- Defects injected:
--   D1  dim_customer  300 rows email = NULL         Completeness
--   D2  dim_customer  10  rows duplicate is_current Uniqueness
--   D3  dim_customer  200 rows email = 'n/a'        Validity
--   D4  dim_customer  50  rows segment typo         Validity
--   D5  dim_product   15  rows list_price = 0       Validity
--   D6  dim_product   10  rows cost > list          Accuracy
--   D7  fact_sales    50  orphan customer_key rows  Consistency
--   D8  fact_sales    100 rows quantity = -1        Validity
--
-- Run in: DBeaver → retaildw_dq connection → whole file (Ctrl+Alt+X)
-- ============================================================

BEGIN;


-- ============================================================
-- D1 — Completeness: NULL emails on 300 rows
-- Target: customer_keys 1-300 (first 300 customers, deterministic)
-- ============================================================

UPDATE warehouse.dim_customer
   SET email = NULL
 WHERE customer_key BETWEEN 1 AND 300;

-- Verification row
SELECT 'D1' AS defect,
       'Completeness' AS dimension,
       COUNT(*) AS affected_rows,
       'email = NULL on customer_keys 1-300' AS description
  FROM warehouse.dim_customer
 WHERE email IS NULL;


-- ============================================================
-- D2 — Uniqueness: duplicate customer_id with both is_current=TRUE
-- Target: duplicates of customer_ids at customer_keys 1001-1010
-- Strategy: INSERT 10 new rows that reuse the customer_id from
-- existing customers 1001-1010, with fresh customer_keys but
-- is_current=TRUE.
-- ============================================================

INSERT INTO warehouse.dim_customer (
    customer_key, customer_id, customer_name, email, city, state,
    zip_code, customer_segment, effective_date, expiry_date, is_current
)
SELECT
    customer_key + 100000 AS customer_key,     -- new unique surrogate key
    customer_id,                               -- SAME business id (the duplicate)
    customer_name || ' [DUP]' AS customer_name,
    email,
    city, state, zip_code,
    customer_segment,
    CURRENT_DATE AS effective_date,            -- new effective date
    DATE '9999-12-31' AS expiry_date,
    TRUE AS is_current                         -- both rows are "current" — defect
  FROM warehouse.dim_customer
 WHERE customer_key BETWEEN 1001 AND 1010;

-- Verification row
SELECT 'D2' AS defect,
       'Uniqueness' AS dimension,
       COUNT(*) AS affected_rows,
       'duplicate customer_ids with both is_current=TRUE' AS description
  FROM (
       SELECT customer_id
         FROM warehouse.dim_customer
        WHERE is_current = TRUE
        GROUP BY customer_id
       HAVING COUNT(*) > 1
  ) dups;


-- ============================================================
-- D3 — Validity: email = 'n/a' on 200 rows (not NULL, but invalid)
-- Target: customer_keys 2001-2200
-- This is the "sentinel value" trap — passes NULL check, fails validity
-- ============================================================

UPDATE warehouse.dim_customer
   SET email = 'n/a'
 WHERE customer_key BETWEEN 2001 AND 2200;

-- Verification row
SELECT 'D3' AS defect,
       'Validity' AS dimension,
       COUNT(*) AS affected_rows,
       'email = ''n/a'' (sentinel value)' AS description
  FROM warehouse.dim_customer
 WHERE email = 'n/a';


-- ============================================================
-- D4 — Validity: customer_segment typo on 50 rows
-- Target: customer_keys 3001-3050
-- 'Platnium' (sic) instead of 'Premium' — misspelled enum value
-- ============================================================

UPDATE warehouse.dim_customer
   SET customer_segment = 'Platnium'    -- deliberate typo (missing 'i')
 WHERE customer_key BETWEEN 3001 AND 3050;

-- Verification row
SELECT 'D4' AS defect,
       'Validity' AS dimension,
       COUNT(*) AS affected_rows,
       'customer_segment = ''Platnium'' typo' AS description
  FROM warehouse.dim_customer
 WHERE customer_segment = 'Platnium';


-- ============================================================
-- D5 — Validity: list_price = 0 on 15 products
-- Target: product_keys 101-115
-- Challenge file DQ-003: "150 products with list_price = 0"
-- ============================================================

UPDATE warehouse.dim_product
   SET list_price = 0
 WHERE product_key BETWEEN 101 AND 115;

-- Verification row
SELECT 'D5' AS defect,
       'Validity' AS dimension,
       COUNT(*) AS affected_rows,
       'list_price = 0 on products' AS description
  FROM warehouse.dim_product
 WHERE list_price = 0;


-- ============================================================
-- D6 — Accuracy: cost_price > list_price on 10 products
-- Target: product_keys 201-210
-- Set cost = list + 50 to guarantee inversion.
-- Challenge file DQ-004 (adapted — their "negative cost_price" is
--   really about the cost < list invariant being broken).
-- ============================================================

UPDATE warehouse.dim_product
   SET cost_price = list_price + 50
 WHERE product_key BETWEEN 201 AND 210;

-- Verification row
SELECT 'D6' AS defect,
       'Accuracy' AS dimension,
       COUNT(*) AS affected_rows,
       'cost_price > list_price (logically inverted)' AS description
  FROM warehouse.dim_product
 WHERE cost_price > list_price;


-- ============================================================
-- D7 — Consistency: orphan fact_sales rows with bad customer_key
-- Target: insert 50 new fact rows, each with customer_key = 999999
-- (value guaranteed to not exist in dim_customer).
-- Challenge file DQ-005: orphan FK.
-- ============================================================

INSERT INTO warehouse.fact_sales (
    sales_key, date_key, customer_key, product_key, store_key,
    order_id, order_line_num, quantity, unit_price, unit_cost,
    discount_amount, net_revenue, gross_profit, tax_amount
)
SELECT
    900000000000 + gs AS sales_key,   -- far above existing max sales_key
    20240615 AS date_key,             -- valid date_key
    999999 AS customer_key,           -- ORPHAN — does not exist in dim_customer
    500 AS product_key,               -- valid product_key
    50  AS store_key,                 -- valid store_key
    'ORD-ORPHAN-' || LPAD(gs::text, 4, '0') AS order_id,
    1 AS order_line_num,
    2 AS quantity,
    100.00 AS unit_price,
    60.00 AS unit_cost,
    5.00 AS discount_amount,
    195.00 AS net_revenue,
    75.00 AS gross_profit,
    15.60 AS tax_amount
  FROM generate_series(1, 50) AS gs;

-- Verification row
SELECT 'D7' AS defect,
       'Consistency' AS dimension,
       COUNT(*) AS affected_rows,
       'orphan fact_sales.customer_key = 999999' AS description
  FROM warehouse.fact_sales f
  LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key
 WHERE c.customer_key IS NULL;


-- ============================================================
-- D8 — Validity: quantity = -1 on 100 fact rows (returns mixed with sales)
-- Target: sales_keys from existing rows, first 100 of a deterministic set
-- Challenge file DQ-006: "200 records with quantity < 0" — scaled to 100.
-- ============================================================

UPDATE warehouse.fact_sales
   SET quantity = -1
 WHERE sales_key IN (
       SELECT sales_key
         FROM warehouse.fact_sales
        ORDER BY sales_key
        LIMIT 100
 );

-- Verification row
SELECT 'D8' AS defect,
       'Validity' AS dimension,
       COUNT(*) AS affected_rows,
       'quantity = -1 on fact rows' AS description
  FROM warehouse.fact_sales
 WHERE quantity = -1;


-- ============================================================
-- FINAL SUMMARY — Consolidated defect report
-- ============================================================

SELECT 'D1' AS defect, 'Completeness' AS dimension,
       (SELECT COUNT(*) FROM warehouse.dim_customer WHERE email IS NULL) AS rows,
       300 AS expected
UNION ALL
SELECT 'D2', 'Uniqueness',
       (SELECT COUNT(*) FROM (
           SELECT customer_id FROM warehouse.dim_customer
            WHERE is_current = TRUE
            GROUP BY customer_id HAVING COUNT(*) > 1
        ) d), 10
UNION ALL
SELECT 'D3', 'Validity',
       (SELECT COUNT(*) FROM warehouse.dim_customer WHERE email = 'n/a'), 200
UNION ALL
SELECT 'D4', 'Validity',
       (SELECT COUNT(*) FROM warehouse.dim_customer WHERE customer_segment = 'Platnium'), 50
UNION ALL
SELECT 'D5', 'Validity',
       (SELECT COUNT(*) FROM warehouse.dim_product WHERE list_price = 0), 15
UNION ALL
SELECT 'D6', 'Accuracy',
       (SELECT COUNT(*) FROM warehouse.dim_product WHERE cost_price > list_price), 10
UNION ALL
SELECT 'D7', 'Consistency',
       (SELECT COUNT(*) FROM warehouse.fact_sales f
          LEFT JOIN warehouse.dim_customer c ON f.customer_key = c.customer_key
         WHERE c.customer_key IS NULL), 50
UNION ALL
SELECT 'D8', 'Validity',
       (SELECT COUNT(*) FROM warehouse.fact_sales WHERE quantity = -1), 100
ORDER BY defect;


COMMIT;