
create unlogged table temp_pse_data_pull as SELECT
    supervisor_id,
    sum(pse_eligible) as pse_eligible,
    SUM( CASE WHEN ('2020-01-31'-dob)/30.4>36 THEN valid_all_registered_in_month ELSE 0 END)  as all_3_6_not_migrated,
    SUM(CASE WHEN ('2020-01-31'-dob)/30.4>36 and valid_all_registered_in_month=1 and valid_in_month=0  THEN 1 ELSE 0 END) as all_3_6_not_migrated_not_seeking_service,
    SUM(CASE WHEN ('2020-01-31'-dob)/30.4>36 and open_in_month=1 and alive_in_month=1 and valid_all_registered_in_month=0  THEN 1 ELSE 0 END) as all_3_6_migrated,
    SUM(CASE WHEN ('2020-01-31'-dob)/30.4>36 and ('2019-12-31'-dob)/30.4<=36 and dob::date != '2017-01-01' THEN valid_in_month ELSE 0 END) as all_not_migrated_turning_3_this_month
from child_health_monthly where month='2020-01-01'
group by supervisor_id;


COPY(SELECT
    state_name,
    district_name,
    sum(all_3_6_not_migrated) as "# children (3-6 yrs)",
    sum(all_3_6_not_migrated_not_seeking_service) as "# children (3-6 yrs) opted out of all aww services, but not migrated",
    sum(all_3_6_migrated) as "Number of children (3-6) migrated",
    sum(all_not_migrated_turning_3_this_month) as "Number of children turning 3 this month",
    sum(pse_eligible) as "# children (3-6 yrs) eligible for PSE"
from temp_pse_data_pull t join awc_location_local a on a.supervisor_id=t.supervisor_id where aggregation_level=4 and state_is_test=0 group by state_name,district_name order by state_name,district_name asc)TO '/tmp/pse_data_Jan_2020.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
​






