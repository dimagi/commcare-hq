

COPY(select
    state_name,
    sum(nutrition_status_moderately_underweight) + sum(nutrition_status_severely_underweight) as underweight,
    sum(nutrition_status_weighed) as under_eligible,
    CASE WHEN sum(nutrition_status_weighed)>0 THEN trunc(((sum(nutrition_status_moderately_underweight) + sum(nutrition_status_severely_underweight))/sum(nutrition_status_weighed)::float*100)::numeric,2) ELSE 0 END underweight_percent

from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1 and (age_tranche::integer<>72 OR age_tranche is null) group by state_name) TO '/tmp/underweight_night.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(select
    state_name,
    sum(zscore_grading_hfa_moderate) + sum(zscore_grading_hfa_severe) as stunting,
    sum(zscore_grading_hfa_recorded_in_month) as stunting_eligible,
    CASE WHEN sum(zscore_grading_hfa_recorded_in_month)>0 THEN trunc(((sum(zscore_grading_hfa_moderate) + sum(zscore_grading_hfa_severe))/sum(zscore_grading_hfa_recorded_in_month)::float*100)::numeric,2) ELSE 0 END stunting_percent

from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1 and (age_tranche::integer<>72 OR age_tranche is null) group by state_name) TO '/tmp/stunting_night.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(select
    state_name,
    sum(wasting_moderate_v2) + sum(wasting_severe_v2) as wasting,
    sum(zscore_grading_wfh_recorded_in_month) as wasting_eligible,
    CASE WHEN sum(zscore_grading_wfh_recorded_in_month)>0 THEN trunc(((sum(wasting_moderate_v2) + sum(wasting_severe_v2))/sum(zscore_grading_wfh_recorded_in_month)::float*100)::numeric,2) ELSE 0 END wasting_percent

from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1 and (age_tranche::integer<>72 OR age_tranche is null) group by state_name) TO '/tmp/wasting_night.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(low_birth_weight_in_month) as low_birth_weight_in_month,
    sum(weighed_and_born_in_month) as weighed_and_born_in_month,
    CASE WHEN sum(weighed_and_born_in_month)>0 THEN trunc((sum(low_birth_weight_in_month)/sum(weighed_and_born_in_month)::float*100)::numeric,2) ELSE 0 END lbw_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/lbw_percent.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(institutional_delivery_in_month) as institutional_delivery,
    sum(delivered_in_month) as delivered_in_month,
    CASE WHEN sum(delivered_in_month)>0 THEN trunc((sum(institutional_delivery_in_month)/sum(delivered_in_month)::float*100)::numeric, 2) ELSE 0 END as instituional_delivery_percent
from agg_ccs_record_monthly where aggregation_level=1 and month='2019-10-01' group by state_name) TO  '/tmp/institutional_delivery.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(select
    state_name,
    sum(bf_at_birth) as bf_at_birth,
    sum(born_in_month) as born_in_month,
    CASE WHEN sum(born_in_month)>0 THEN trunc((sum(bf_at_birth)/sum(born_in_month)::float*100)::numeric,2) ELSE 0 END bf_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/bf_at_birth.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(ebf_in_month) as ebf
    sum(ebf_eligible) as ebf_eligible,
    CASE WHEN sum(ebf_eligible)>0 THEN trunc((sum(ebf_in_month)/sum(ebf_eligible)::float*100)::numeric,2) ELSE 0 END ebf_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/ebfcsv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(select
    state_name,
    sum(cf_initiation_in_month) as cf
    sum(cf_initiation_eligible) as cf_eligible,
    CASE WHEN sum(cf_initiation_eligible)>0 THEN trunc((sum(cf_initiation_in_month)/sum(cf_initiation_eligible)::float*100)::numeric,2) ELSE 0 END cf_percent
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/cf.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(nutrition_status_weighed) as weighed
    sum(wer_eligible) as weighing_eligible,
    CASE WHEN sum(wer_eligible)>0 THEN trunc((sum(nutrition_status_weighed)/sum(wer_eligible)::float*100)::numeric,2) ELSE 0 END weighin_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/weighin_percentage.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(height_measured_in_month) as height_measured_in_month
    sum(height_eligible) as height_eligible,
    CASE WHEN sum(height_eligible)>0 THEN trunc((sum(height_measured_in_month)/sum(height_eligible)::float*100)::numeric,2) ELSE 0 END height_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/height_percentage.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(
    select
state_name,
total_thr_candidates,
thr_given_21_days,
CASE WHEN total_thr_candidates>0 THEN trunc((thr_given_21_days/total_thr_candidates::float*100)::numeric,2) ELSE 0 END as percent_thr_21
from service_delivery_monthly where aggregation_level=1 and month='2019-10-01') TO '/tmp/total_thr.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(rations_21_plus_distributed) as rations_21_plus_distributed,
    sum(thr_eligible) as thr_eligible,
    CASE WHEN sum(thr_eligible)>0 THEN trunc((sum(rations_21_plus_distributed)/sum(thr_eligible)::float*100)::numeric, 2) ELSE 0 END as thr_eligible
from agg_ccs_record_monthly where aggregation_level=1 and month='2019-10-01' group by state_name) TO  '/tmp/mother_thr.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(select
    state_name,
    sum(pse_attended_21_days) as pse_attended_21_days,
    sum(children_3_6) as children_3_6,
    CASE WHEN sum(children_3_6)>0 THEN trunc((sum(pse_attended_21_days)/sum(children_3_6)::float*100)::numeric, 2) ELSE 0 END as pse_percent
from service_delivery_monthly where aggregation_level=1 and month='2019-10-01' group by state_name) TO  '/tmp/child_pse.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(lunch_count_21_days) as lunch_count_21_days,
    sum(children_3_6) as children_3_6,
    CASE WHEN sum(children_3_6)>0 THEN trunc((sum(lunch_count_21_days)/sum(children_3_6)::float*100)::numeric, 2) ELSE 0 END as pse_percent
from service_delivery_monthly where aggregation_level=1 and month='2019-10-01' group by state_name) TO  '/tmp/child_lunch.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



COPY(SELECT
    state_name,
    expected_visits,
    valid_visits,
    CASE WHEN expected_visits>0 THEN trunc((valid_visits/expected_visits::float*100)::numeric,2) ELSE 0 END as percent_visit
from service_delivery_monthly where aggregation_level=1 and month='2019-10-01')TO '/tmp/home_visit_night.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


COPY(select
    state_name,
    sum(rations_21_plus_distributed) as rations_21_plus_distributed
    sum(thr_eligible) as thr_eligible,
    CASE WHEN sum(thr_eligible)>0 THEN trunc((sum(rations_21_plus_distributed)/sum(thr_eligible)::float*100)::numeric,2) ELSE 0 END thr_child_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/thr_child_percentage.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
