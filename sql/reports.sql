-- Part 1, Task 3: report queries.
-- Each query was run against the loaded, UNCLEANED data; its exact output is pasted above it.
-- Run schema.sql then seed_data.sql FIRST. Query (i) alters the table, so re-run both before re-running this file.

-- a) Order totals (COUNT, total revenue, average order value)
-- OUTPUT:
--   total_orders | total_revenue | avg_order_value
--   180 | 99860.20 | 554.78
SELECT COUNT(*) AS total_orders, ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue, ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;

-- b) COUNT(*) vs COUNT(column): 15 orders have no rating yet
-- OUTPUT:
--   total_orders | rated_orders | unrated_orders
--   180 | 165 | 15
SELECT COUNT(*) AS total_orders, COUNT(rating) AS rated_orders, COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;

-- c1) LEFT JOIN + GROUP BY + HAVING: customer with zero orders
-- OUTPUT:
--   customer_id | name | order_count
--   C045 | Vihaan | 0
SELECT c.customer_id, c.name, COUNT(o.order_id) AS order_count
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- c2) Independent check with NOT IN (must return the same customer)
-- OUTPUT:
--   customer_id | name
--   C045 | Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id
FROM orders);

-- d) Cities with return rate above 20%
-- OUTPUT:
--   city | total_orders | returned_orders | return_rate_pct
--   Jaipur | 19 | 8 | 42.10
--   Lucknow | 49 | 15 | 30.60
--   Bangalore | 33 | 8 | 24.20
SELECT c.city, COUNT(o.order_id) AS total_orders, SUM(o.returned) AS returned_orders, ROUND(SUM(o.returned) * 100.0 / COUNT(o.order_id), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- e1) Top 5 customers by spend
-- customer_id ASC is the tie-break: it makes the ordering deterministic when two
-- customers have equal total_spend, so LIMIT/OFFSET pagination is reproducible.
-- OUTPUT:
--   customer_id | name | total_spend
--   C043 | Reyansh | 12920.00
--   C026 | Isha | 8371.60
--   C008 | Meera | 4564.60
--   C011 | Arjun | 4111.00
--   C042 | Sanya | 3785.00
SELECT c.customer_id, c.name, ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

-- e2) Ranks 3-5 using OFFSET (same ordering, skip the first 2 rows)
-- OUTPUT:
--   customer_id | name | total_spend
--   C008 | Meera | 4564.60
--   C011 | Arjun | 4111.00
--   C042 | Sanya | 3785.00
SELECT c.customer_id, c.name, ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

-- f) Three-table JOIN grouped by category
-- OUTPUT:
--   category | order_count | category_revenue
--   Haircare | 54 | 44956.10
--   Skincare | 60 | 27346.00
--   Babycare | 30 | 16805.00
--   PersonalCare | 36 | 10753.10
SELECT p.category, COUNT(o.order_id) AS order_count, ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;

-- g) LIKE: customers whose name starts with 'A' (expect 10 rows)
-- OUTPUT:
--   customer_id | name
--   C001 | Aarav
--   C003 | Aditi
--   C004 | Ananya
--   C011 | Arjun
--   C021 | Aryan
--   C030 | Anika
--   C031 | Aditya
--   C036 | Aisha
--   C041 | Ayaan
--   C044 | Aria
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%';

-- h) DISTINCT acquisition sources (expect 4)
-- OUTPUT:
--   acquisition_source
--   Organic
--   Referral
--   Ad
--   Social
SELECT DISTINCT acquisition_source
FROM customers;

-- i) ALTER TABLE + UPDATE with CASE (no WHERE: every row gets a value)
-- MySQL Workbench note: if it complains about safe update mode, run  SET SQL_SAFE_UPDATES = 0;  first.
-- OUTPUT of the verification query below:
--   loyalty_tier | COUNT(*)
--   Silver | 17
--   Gold | 28
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);
UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;
SELECT loyalty_tier, COUNT(*) FROM customers GROUP BY loyalty_tier;
