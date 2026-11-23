-- Analytics queries run after every load. Each "-- name:" block becomes reports/<name>.csv.
-- Written to run on both SQLite and PostgreSQL (joins, GROUP BY, CTEs, window functions).

-- name: revenue_by_month
SELECT order_month,
       COUNT(*) AS orders,
       ROUND(SUM(total_amount), 2) AS revenue
FROM fact_orders
WHERE status = 'completed'
GROUP BY order_month
ORDER BY order_month;

-- name: running_revenue
WITH monthly AS (
    SELECT order_month, SUM(total_amount) AS revenue
    FROM fact_orders
    WHERE status = 'completed'
    GROUP BY order_month
)
SELECT order_month,
       ROUND(revenue, 2) AS revenue,
       ROUND(SUM(revenue) OVER (ORDER BY order_month), 2) AS cumulative_revenue,
       ROUND(revenue - LAG(revenue) OVER (ORDER BY order_month), 2) AS change_vs_prev_month
FROM monthly
ORDER BY order_month;

-- name: top_customers
SELECT customer_id, name, country, revenue,
       RANK() OVER (ORDER BY revenue DESC) AS revenue_rank
FROM (
    SELECT c.customer_id, c.name, c.country, ROUND(SUM(o.total_amount), 2) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON c.customer_id = o.customer_id
    WHERE o.status = 'completed'
    GROUP BY c.customer_id, c.name, c.country
) AS per_customer
ORDER BY revenue_rank
LIMIT 10;

-- name: category_performance
SELECT p.category,
       SUM(o.quantity) AS units_sold,
       ROUND(SUM(o.total_amount), 2) AS revenue,
       ROUND(100.0 * SUM(o.total_amount) / SUM(SUM(o.total_amount)) OVER (), 1) AS pct_of_revenue
FROM fact_orders o
JOIN dim_products p ON p.product_id = o.product_id
WHERE o.status = 'completed'
GROUP BY p.category
ORDER BY revenue DESC;

-- name: order_status_mix
SELECT status,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_orders
FROM fact_orders
GROUP BY status
ORDER BY orders DESC;
