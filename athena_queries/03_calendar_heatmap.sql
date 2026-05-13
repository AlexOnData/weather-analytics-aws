-- Q3: One row per day for the calendar heatmap.
SELECT
    date,
    city,
    EXTRACT(YEAR FROM date)  AS year,
    EXTRACT(MONTH FROM date) AS month,
    EXTRACT(DAY FROM date)   AS day,
    EXTRACT(DOW FROM date)   AS day_of_week_num,
    ROUND(avg_temp, 1)         AS avg_temperature,
    dominant_weather,
    ROUND(total_precipitation, 1) AS precipitation_mm
FROM daily_summary
WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
ORDER BY city, date;
