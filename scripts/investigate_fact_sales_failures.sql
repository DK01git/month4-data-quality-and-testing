-- ============================================================
-- Month 4 — Investigation of unexpected fact_sales FAILs
-- Purpose: Characterize the 4 unpredicted FAILs from the GX run
-- Run in:  DBeaver (retaildw_dq connection as dataeng)
-- Context: Expected 2 FAILs (D7, D8); observed 6.
--          Investigations below classify the additional 4.
-- ============================================================


-- ------------------------------------------------------------
-- INV-1: Pre-existing duplicate (order_id, order_line_num)
-- Finding: 1000+ duplicate combinations, up to 7 repetitions each.
-- Classification: Uniqueness; source Month 3 data generation, not
-- Month 4 injection.
-- ------------------------------------------------------------

SELECT order_id, order_line_num, COUNT(*) AS dup_count
FROM warehouse.fact_sales
GROUP BY order_id, order_line_num
HAVING COUNT(*) > 1
ORDER BY dup_count DESC
LIMIT 10;


-- ------------------------------------------------------------
-- INV-2: net_revenue arithmetic cascade from D8
-- Finding: 100 rows with quantity=-1 where net_revenue was NOT
-- recomputed. ABS(diff) ranges 3620-5160.
-- Classification: Accuracy; D8 compound effect.
-- ------------------------------------------------------------

SELECT sales_key, quantity, unit_price, discount_amount, net_revenue,
       (quantity * unit_price - discount_amount) AS computed_revenue,
       ABS(net_revenue - (quantity * unit_price - discount_amount)) AS diff
FROM warehouse.fact_sales
WHERE ABS(net_revenue - (quantity * unit_price - discount_amount)) > 0.01
ORDER BY diff DESC
LIMIT 10;


-- ------------------------------------------------------------
-- INV-3: gross_profit arithmetic cascade from D8
-- Finding: Same 100 rows as INV-2. quantity=-1 but gross_profit
-- unchanged; formula gross_profit = net_revenue - qty*unit_cost
-- now inconsistent.
-- Classification: Accuracy; D8 compound effect.
-- ------------------------------------------------------------

SELECT sales_key, quantity, unit_cost, net_revenue, gross_profit,
       (net_revenue - (quantity * unit_cost)) AS computed_profit,
       ABS(gross_profit - (net_revenue - (quantity * unit_cost))) AS diff
FROM warehouse.fact_sales
WHERE ABS(gross_profit - (net_revenue - (quantity * unit_cost))) > 0.01
ORDER BY diff DESC
LIMIT 10;


-- ------------------------------------------------------------
-- INV-4: Pre-existing negative tax_amount
-- Finding: 747 rows with tax_amount < 0.
-- Classification: Validity; source Month 3 data generation, not
-- Month 4 injection.
-- ------------------------------------------------------------

SELECT 'tax_amount below min' AS check, COUNT(*) AS violations
  FROM warehouse.fact_sales WHERE tax_amount < 0
UNION ALL
SELECT 'net_revenue below min', COUNT(*)
  FROM warehouse.fact_sales WHERE net_revenue < -10000
UNION ALL
SELECT 'gross_profit below min', COUNT(*)
  FROM warehouse.fact_sales WHERE gross_profit < -10000;


-- ------------------------------------------------------------
-- Sample negative-tax rows for evidence in deliverable #5
-- ------------------------------------------------------------

SELECT sales_key, date_key, customer_key, product_key,
       quantity, unit_price, net_revenue, tax_amount
FROM warehouse.fact_sales
WHERE tax_amount < 0
ORDER BY tax_amount ASC
LIMIT 10;