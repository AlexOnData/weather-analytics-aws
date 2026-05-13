-- Q7: Hourly detail view used by the data table widget.
-- Uses {city}, {start_date}, {end_date} placeholders.
SELECT
    timestamp,
    city,
    ROUND(temperature_c, 1)    AS temperature_c,
    ROUND(feels_like_c, 1)     AS feels_like_c,
    ROUND(precipitation_mm, 1) AS precipitation_mm,
    ROUND(wind_speed_kmh, 1)   AS wind_speed_kmh,
    humidity_pct,
    ROUND(pressure_hpa, 1)     AS pressure_hpa,
    cloud_cover_pct,
    weather_description,
    weather_category,
    wind_category,
    is_extreme_event
FROM weather_hourly
WHERE city = '{city}'
  AND date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
ORDER BY timestamp
LIMIT 10000;
