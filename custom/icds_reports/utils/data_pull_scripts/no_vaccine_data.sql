SELECT
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    child_health.awc_id,
    SUM(valid_in_month),
    COUNT(*) FILTER (where
                      (NOT (date_trunc('MONTH', child_tasks.due_list_date_1g_dpt_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_dpt_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_dpt_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_7gdpt_booster_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_0g_hep_b_0) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_hep_b_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_hep_b_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_hep_b_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_ipv) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_je_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_je_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_measles_booster) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_measles) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_penta_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_penta_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_penta_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_rv_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_rv_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_rv_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_vit_a_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_vit_a_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_4) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_5) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_6) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_7) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_8) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_7g_vit_a_9) <= '2019-11-01'))
                      AND age_in_months<=1
    ) AS not_given_vaccine_0_1m,
    COUNT(*) FILTER (where
                      (NOT (date_trunc('MONTH', child_tasks.due_list_date_1g_dpt_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_dpt_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_dpt_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_7gdpt_booster_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_0g_hep_b_0) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_hep_b_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_hep_b_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_hep_b_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_ipv) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_je_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_je_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_measles_booster) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_measles) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_penta_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_penta_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_penta_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_rv_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_rv_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_rv_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_vit_a_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_vit_a_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_4) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_5) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_6) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_7) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_8) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_7g_vit_a_9) <= '2019-11-01'))
                      AND (age_in_months>1 and age_in_months<=3)
    ) AS not_given_vaccine_1_3m,
    COUNT(*) FILTER (where
                      (NOT (date_trunc('MONTH', child_tasks.due_list_date_1g_dpt_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_dpt_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_dpt_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_dpt_booster1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_7gdpt_booster_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_0g_hep_b_0) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_hep_b_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_hep_b_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_hep_b_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_ipv) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_je_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_je_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_measles_booster) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_measles) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_penta_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_penta_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_penta_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_1g_rv_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_2g_rv_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_3g_rv_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_4g_vit_a_1) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_5g_vit_a_2) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_3) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_4) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_5) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_6) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_7) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_6g_vit_a_8) <= '2019-11-01' OR
                      date_trunc('MONTH', child_tasks.due_list_date_7g_vit_a_9) <= '2019-11-01'))
                      AND (age_in_months>3 and age_in_months<=6)
    ) AS not_given_vaccine_3_6m

FROM   child_health_monthly child_health
    left join awc_location ON
        awc_location.supervisor_id = child_health.supervisor_id AND
        awc_location.doc_id = child_health.awc_id
    left join "ucr_icds-cas_static-child_tasks_cases_3548e54b" child_tasks ON
        child_health.case_id = child_tasks.child_health_case_id AND
        child_health.supervisor_id = child_tasks.supervisor_id

WHERE child_health.age_in_months<=6 and child_health.valid_in_month=1 and child_health.month='2019-11-01' and awc_location.aggregation_level=5
GROUP BY state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    child_health.awc_id limit 1

/*
 Limit  (cost=0.00..0.00 rows=0 width=0)
   ->  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
         Group Key: remote_scan.state_name, remote_scan.district_name, remote_scan.block_name, remote_scan.supervisor_name, remote_scan.awc_name, remote_scan.awc_id
         ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
               Task Count: 64
               Tasks Shown: One of 64
               ->  Task
                     Node: host=100.71.184.232 port=6432 dbname=icds_ucr
                     ->  Finalize GroupAggregate  (cost=533426.39..533427.87 rows=2 width=140)
                           Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, child_health.awc_id
                           ->  Gather Merge  (cost=533426.39..533427.72 rows=5 width=140)
                                 Workers Planned: 5
                                 ->  Partial GroupAggregate  (cost=532426.32..532427.04 rows=1 width=140)
                                       Group Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, child_health.awc_id
                                       ->  Sort  (cost=532426.32..532426.32 rows=1 width=236)
                                             Sort Key: awc_location.state_name, awc_location.district_name, awc_location.block_name, awc_location.supervisor_name, awc_location.awc_name, child_health.awc_id
                                             ->  Nested Loop Left Join  (cost=1.53..532426.31 rows=1 width=236)
                                                   ->  Nested Loop  (cost=1.11..532424.98 rows=1 width=186)
                                                         ->  Parallel Index Scan using chm_month_supervisor_id_102648 on child_health_monthly_102648 child_health  (cost=0.56..514216.96 rows=10541 width=111)
                                                               Index Cond: (month = '2019-11-01'::date)
                                                               Filter: ((age_in_months <= 6) AND (valid_in_month = 1))
                                                         ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc_location  (cost=0.55..1.72 rows=1 width=138)
                                                               Index Cond: (doc_id = child_health.awc_id)
                                                               Filter: ((aggregation_level = 5) AND (child_health.supervisor_id = supervisor_id))
                                                   ->  Index Scan using "ix_ucr_icds-cas_static-child_tasks_cases_3548e5_9585e11e_102906" on "ucr_icds-cas_static-child_tasks_cases_3548e54b_102906" child_tasks  (cost=0.42..1.32 rows=1 width=190)
                                                         Index Cond: (child_health.case_id = child_health_case_id)
                                                         Filter: (child_health.supervisor_id = supervisor_id)
(27 rows)
*/
