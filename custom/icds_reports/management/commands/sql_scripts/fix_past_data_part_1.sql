UPDATE child_health_monthly
SET
      lunch_count = CASE WHEN pse_eligible=1 THEN lunch_count ELSE NULL END
WHERE month='{start_date}';
