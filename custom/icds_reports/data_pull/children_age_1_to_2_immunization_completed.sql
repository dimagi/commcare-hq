COPY(
select state_name, district_name,
SUM(valid_in_month) as child_1_2,
SUM(COALESCE(fully_immunized_on_time,0)+COALESCE(fully_immunized_late,0)) as immunization_complete
from agg_child_health_monthly
where month='2019-10-01' and aggregation_level=2 and age_tranche::INTEGER BETWEEN 13 AND 24
group by state_name, district_name
)
to '/tmp/immunization_completed_age_1_to_2.csv' DELIMITER ',' CSV HEADER;
