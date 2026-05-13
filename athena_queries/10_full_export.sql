-- Q10: Full hourly export, used for the Excel/CSV download.
-- Uses {city} and {year} placeholders.
SELECT
    date,
    CAST(hour AS VARCHAR) || ':00' AS hour,
    city,
    season,
    day_of_week,
    CASE WHEN is_daytime THEN 'Day' ELSE 'Night' END AS time_of_day,
    ROUND(temperature_c, 1)    AS temperature_c,
    ROUND(feels_like_c, 1)     AS feels_like_c,
    ROUND(precipitation_mm, 1) AS precipitation_mm,
    ROUND(wind_speed_kmh, 1)   AS wind_speed_kmh,
    wind_category,
    humidity_pct,
    ROUND(pressure_hpa, 1)     AS pressure_hpa,
    cloud_cover_pct,
    weather_description,
    weather_category,
    CASE WHEN is_extreme_event THEN 'Yes' ELSE 'No' END AS extreme_event
FROM weather_hourly
WHERE city = '{city}'
  AND year = {year}
ORDER BY date, hour
LIMIT 50000;
