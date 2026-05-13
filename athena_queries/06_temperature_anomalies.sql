-- Q6: Daily temperature vs. the historical average for the same calendar day.
WITH historical_avg AS (
    SELECT
        city,
        EXTRACT(MONTH FROM date) AS month,
        EXTRACT(DAY FROM date)   AS day,
        ROUND(AVG(avg_temp), 2)  AS historical_avg_temp
    FROM daily_summary
    WHERE year < EXTRACT(YEAR FROM CURRENT_DATE)
    GROUP BY city, EXTRACT(MONTH FROM date), EXTRACT(DAY FROM date)
),
current_year AS (
    SELECT
        date,
        city,
        EXTRACT(MONTH FROM date) AS month,
        EXTRACT(DAY FROM date)   AS day,
        avg_temp                 AS current_temp
    FROM daily_summary
    WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
)
SELECT
    c.date,
    c.city,
    ROUND(c.current_temp, 1)                         AS current_temp,
    ROUND(h.historical_avg_temp, 1)                  AS historical_avg,
    ROUND(c.current_temp - h.historical_avg_temp, 1) AS anomaly
FROM current_year c
JOIN historical_avg h
  ON c.city = h.city AND c.month = h.month AND c.day = h.day
ORDER BY c.city, c.date;
