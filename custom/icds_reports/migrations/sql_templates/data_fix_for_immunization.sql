-- CHILD HEALTH MONTHLY 
UPDATE "child_health_monthly" SET
fully_immunized_eligible = 0,
fully_immunized_on_time = 0,
fully_immunized_late = 0

where fully_immunized_eligible = 1 and age_tranche::integer<=12 and month='2019-07-01';


-- AGG CHILD HEALTH, No need of roll up because they will be only zero because its grouped by age_tranche
UPDATE "agg_child_health" agg_child SET
fully_immunized_eligible = 0,
fully_immunized_on_time = 0,
fully_immunized_late = 0
WHERE (
   age_tranche::integer<=12 AND
   month='2019-07-01';
)
