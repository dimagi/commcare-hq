

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
 HashAggregate  (cost=197.65..198.26 rows=22 width=58)
   Group Key: awc_location.state_name
   ->  Hash Left Join  (cost=147.17..194.68 rows=198 width=18)
         Hash Cond: ((months.start_date = agg_child_health.month) AND (awc_location.aggregation_level = agg_child_health.aggregation_level) AND (awc_location.state_id = agg_child_health.state_id) AND (awc_location.district_id = agg_child_health.district_id) AND (awc_location.block_id = agg_child_health.block_id) AND (awc_location.supervisor_id = agg_child_health.supervisor_id) AND (awc_location.doc_id = agg_child_health.awc_id))
         ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
                     Index Cond: (aggregation_level = 1)
               ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
         ->  Hash  (cost=141.55..141.55 rows=189 width=177)
               ->  Append  (cost=0.00..141.55 rows=189 width=177)
                     ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=176)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                     ->  Index Scan using "agg_child_health_2019-10-01_idx_3" on "agg_child_health_2019-10-01" agg_child_health_1  (cost=0.43..140.60 rows=188 width=177)
                           Index Cond: (aggregation_level = 1)
                           Filter: (month = '2019-10-01'::date)
(17 rows)
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
 Subquery Scan on service_delivery_monthly  (cost=47.74..47.83 rows=1 width=58)
   ->  GroupAggregate  (cost=47.74..47.80 rows=1 width=424)
         Group Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, agg_awc.month, agg_awc.num_launched_awcs, agg_awc.num_awcs_conducted_cbe, agg_awc.valid_visits, agg_awc.expected_visits, agg_awc.num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
         ->  Sort  (cost=47.74..47.75 rows=1 width=356)
               Sort Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, agg_awc.num_launched_awcs, agg_awc.num_awcs_conducted_cbe, agg_awc.valid_visits, agg_awc.expected_visits, agg_awc.num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
               ->  Nested Loop Left Join  (cost=8.19..47.73 rows=1 width=356)
                     Join Filter: ((agg_ccs_record.month = months.start_date) AND (agg_ccs_record.aggregation_level = awc_location.aggregation_level) AND (agg_ccs_record.state_id = awc_location.state_id) AND (agg_ccs_record.district_id = awc_location.district_id) AND (agg_ccs_record.block_id = awc_location.block_id) AND (agg_ccs_record.supervisor_id = awc_location.supervisor_id) AND (agg_ccs_record.awc_id = awc_location.doc_id))
                     ->  Nested Loop Left Join  (cost=0.42..35.74 rows=1 width=344)
                           Join Filter: (agg_child_health.month = months.start_date)
                           ->  Nested Loop  (cost=0.42..32.91 rows=1 width=336)
                                 ->  Nested Loop  (cost=0.42..7.85 rows=1 width=332)
                                       ->  Append  (cost=0.00..2.52 rows=2 width=188)
                                             ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=188)
                                                   Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                             ->  Seq Scan on "agg_awc_2019-10-01_1"  (cost=0.00..2.51 rows=1 width=188)
                                                   Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                       ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local awc_location  (cost=0.42..2.66 rows=1 width=308)
                                             Index Cond: (doc_id = agg_awc.awc_id)
                                             Filter: ((aggregation_level = 1) AND (agg_awc.state_id = state_id) AND (agg_awc.district_id = district_id) AND (agg_awc.block_id = block_id) AND (agg_awc.supervisor_id = supervisor_id))
                                 ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                                       Filter: (start_date = '2019-10-01'::date)
                           ->  Append  (cost=0.00..2.81 rows=2 width=177)
                                 ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=176)
                                       Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1) AND (aggregation_level = awc_location.aggregation_level) AND (state_id = awc_location.state_id) AND (district_id = awc_location.district_id) AND (block_id = awc_location.block_id) AND (supervisor_id = awc_location.supervisor_id) AND (awc_id = awc_location.doc_id))
                                 ->  Index Scan using "agg_child_health_2019-10-01_idx_1" on "agg_child_health_2019-10-01"  (cost=0.56..2.80 rows=1 width=177)
                                       Index Cond: ((aggregation_level = awc_location.aggregation_level) AND (aggregation_level = 1) AND (state_id = awc_location.state_id))
                                       Filter: ((month = '2019-10-01'::date) AND (district_id = awc_location.district_id) AND (block_id = awc_location.block_id) AND (supervisor_id = awc_location.supervisor_id) AND (awc_id = awc_location.doc_id))
                     ->  HashAggregate  (cost=7.77..8.66 rows=89 width=73)
                           Group Key: agg_ccs_record.state_id, agg_ccs_record.district_id, agg_ccs_record.block_id, agg_ccs_record.supervisor_id, agg_ccs_record.awc_id, agg_ccs_record.aggregation_level, agg_ccs_record.month
                           ->  Append  (cost=0.00..5.77 rows=89 width=66)
                                 ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=176)
                                       Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                                 ->  Seq Scan on "agg_ccs_record_2019-10-01_1"  (cost=0.00..5.32 rows=88 width=65)
                                       Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(34 rows)
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
