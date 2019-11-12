

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

/*
EXPLAIN for above agg_ccs_record_monthly query
 HashAggregate  (cost=59.12..59.72 rows=22 width=58)
   Group Key: awc_location.state_name
   ->  Hash Left Join  (cost=8.64..56.15 rows=198 width=18)
         Hash Cond: ((months.start_date = agg_ccs_record.month) AND (awc_location.aggregation_level = agg_ccs_record.aggregation_level) AND (awc_location.state_id = agg_ccs_record.state_id) AND (awc_location.district_id = agg_ccs_record.district_id) AND (awc_location.block_id = agg_ccs_record.block_id) AND (awc_location.supervisor_id = agg_ccs_record.supervisor_id) AND (awc_location.doc_id = agg_ccs_record.awc_id))
         ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
                     Index Cond: (aggregation_level = 1)
               ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
         ->  Hash  (cost=5.77..5.77 rows=89 width=66)
               ->  Append  (cost=0.00..5.77 rows=89 width=66)
                     ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=176)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                     ->  Seq Scan on "agg_ccs_record_2019-10-01_1" agg_ccs_record_1  (cost=0.00..5.32 rows=88 width=65)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(16 rows)
*/



COPY(select
    state_name,
    sum(bf_at_birth) as bf_at_birth,
    sum(born_in_month) as born_in_month,
    CASE WHEN sum(born_in_month)>0 THEN trunc((sum(bf_at_birth)/sum(born_in_month)::float*100)::numeric,2) ELSE 0 END bf_percentage
from agg_child_health_monthly where month='2019-10-01' AND aggregation_level=1  group by state_name) TO '/tmp/bf_at_birth.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
EXPLAIN for above child_health query, this should be similar for other child_health queries as other queries are also similar.
 GroupAggregate  (cost=1714503.65..1714507.72 rows=22 width=58)
   Group Key: awc_location.state_name
   ->  Sort  (cost=1714503.65..1714504.15 rows=198 width=18)
         Sort Key: awc_location.state_name
         ->  Nested Loop Left Join  (cost=1000.42..1714496.10 rows=198 width=18)
               Join Filter: ((months.start_date = agg_child_health_1.month) AND (awc_location.aggregation_level = agg_child_health_1.aggregation_level) AND (awc_location.state_id = agg_child_health_1.state_id) AND (awc_location.district_id = agg_child_health_1.district_id) AND (awc_location.block_id = agg_child_health_1.block_id) AND (awc_location.supervisor_id = agg_child_health_1.supervisor_id) AND (awc_location.doc_id = agg_child_health_1.awc_id))
               ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
                     ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
                           Index Cond: (aggregation_level = 1)
                     ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                           ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                 Filter: (start_date = '2019-10-01'::date)
               ->  Materialize  (cost=1000.00..1713313.38 rows=192 width=177)
                     ->  Gather  (cost=1000.00..1713312.42 rows=192 width=177)
                           Workers Planned: 4
                           ->  Parallel Append  (cost=0.00..1712293.22 rows=48 width=177)
                                 ->  Parallel Seq Scan on "agg_child_health_2019-10-01" agg_child_health_1  (cost=0.00..1712292.98 rows=48 width=177)
                                       Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                 ->  Parallel Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=176)
                                       Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(20 rows)
*/

COPY(
    select
state_name,
total_thr_candidates,
thr_given_21_days,
CASE WHEN total_thr_candidates>0 THEN trunc((thr_given_21_days/total_thr_candidates::float*100)::numeric,2) ELSE 0 END as percent_thr_21
from service_delivery_monthly where aggregation_level=1 and month='2019-10-01') TO '/tmp/total_thr.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
/*
EXPLAIN FOR above service_delievery_query should be similar for other sdd query.
 Subquery Scan on service_delivery_monthly  (cost=1713339.30..1713339.70 rows=1 width=58)
   ->  Finalize GroupAggregate  (cost=1713339.30..1713339.67 rows=1 width=424)
         Group Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, "agg_awc_2019-10-01_1".month, "agg_awc_2019-10-01_1".num_launched_awcs, "agg_awc_2019-10-01_1".num_awcs_conducted_cbe, "agg_awc_2019-10-01_1".valid_visits, "agg_awc_2019-10-01_1".expected_visits, "agg_awc_2019-10-01_1".num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
         ->  Gather Merge  (cost=1713339.30..1713339.58 rows=2 width=364)
               Workers Planned: 2
               ->  Partial GroupAggregate  (cost=1712339.28..1712339.33 rows=1 width=364)
                     Group Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, "agg_awc_2019-10-01_1".month, "agg_awc_2019-10-01_1".num_launched_awcs, "agg_awc_2019-10-01_1".num_awcs_conducted_cbe, "agg_awc_2019-10-01_1".valid_visits, "agg_awc_2019-10-01_1".expected_visits, "agg_awc_2019-10-01_1".num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
                     ->  Sort  (cost=1712339.28..1712339.28 rows=1 width=356)
                           Sort Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, "agg_awc_2019-10-01_1".num_launched_awcs, "agg_awc_2019-10-01_1".num_awcs_conducted_cbe, "agg_awc_2019-10-01_1".valid_visits, "agg_awc_2019-10-01_1".expected_visits, "agg_awc_2019-10-01_1".num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
                           ->  Nested Loop Left Join  (cost=1712302.73..1712339.27 rows=1 width=356)
                                 Join Filter: ((agg_ccs_record.month = months.start_date) AND (agg_ccs_record.aggregation_level = awc_location.aggregation_level) AND (agg_ccs_record.state_id = awc_location.state_id) AND (agg_ccs_record.district_id = awc_location.district_id) AND (agg_ccs_record.block_id = awc_location.block_id) AND (agg_ccs_record.supervisor_id = awc_location.supervisor_id) AND (agg_ccs_record.awc_id = awc_location.doc_id))
                                 ->  Parallel Hash Left Join  (cost=1712294.96..1712327.27 rows=1 width=344)
                                       Hash Cond: ((months.start_date = "agg_child_health_2019-10-01".month) AND (awc_location.aggregation_level = "agg_child_health_2019-10-01".aggregation_level) AND (awc_location.state_id = "agg_child_health_2019-10-01".state_id) AND (awc_location.district_id = "agg_child_health_2019-10-01".district_id) AND (awc_location.block_id = "agg_child_health_2019-10-01".block_id) AND (awc_location.supervisor_id = "agg_child_health_2019-10-01".supervisor_id) AND (awc_location.doc_id = "agg_child_health_2019-10-01".awc_id))
                                       ->  Nested Loop  (cost=0.42..32.70 rows=1 width=336)
                                             ->  Nested Loop  (cost=0.42..7.64 rows=1 width=332)
                                                   ->  Parallel Append  (cost=0.00..2.31 rows=2 width=188)
                                                         ->  Parallel Seq Scan on "agg_awc_2019-10-01_1"  (cost=0.00..2.30 rows=1 width=188)
                                                               Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                                         ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=188)
                                                               Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                                   ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..2.66 rows=1 width=308)
                                                         Index Cond: (doc_id = "agg_awc_2019-10-01_1".awc_id)
                                                         Filter: ((aggregation_level = 1) AND ("agg_awc_2019-10-01_1".state_id = state_id) AND ("agg_awc_2019-10-01_1".district_id = district_id) AND ("agg_awc_2019-10-01_1".block_id = block_id) AND ("agg_awc_2019-10-01_1".supervisor_id = supervisor_id))
                                             ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                                   Filter: (start_date = '2019-10-01'::date)
                                       ->  Parallel Hash  (cost=1712293.22..1712293.22 rows=48 width=177)
                                             ->  Parallel Append  (cost=0.00..1712293.22 rows=48 width=177)
                                                   ->  Parallel Seq Scan on "agg_child_health_2019-10-01"  (cost=0.00..1712292.98 rows=48 width=177)
                                                         Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                                   ->  Parallel Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=176)
                                                         Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                 ->  HashAggregate  (cost=7.77..8.66 rows=89 width=73)
                                       Group Key: agg_ccs_record.state_id, agg_ccs_record.district_id, agg_ccs_record.block_id, agg_ccs_record.supervisor_id, agg_ccs_record.awc_id, agg_ccs_record.aggregation_level, agg_ccs_record.month
                                       ->  Append  (cost=0.00..5.77 rows=89 width=66)
                                             ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=176)
                                                   Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                             ->  Seq Scan on "agg_ccs_record_2019-10-01_1"  (cost=0.00..5.32 rows=88 width=65)
                                                   Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(38 rows)
*/




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
