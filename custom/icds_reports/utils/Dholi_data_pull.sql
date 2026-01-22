 COPY (
            SELECT t.awc_id,t.case_id,t.month,t.age_in_months,t.open_in_month,t.alive_in_month,t.wer_eligible,t.nutrition_status_last_recorded,t.current_month_nutrition_status,t.nutrition_status_weighed,t.num_rations_distributed,t.pse_eligible,t.pse_days_attended,t.born_in_month,t.low_birth_weight_born_in_month,t.bf_at_birth_born_in_month,t.ebf_eligible,t.ebf_in_month,t.ebf_not_breastfeeding_reason,t.ebf_drinking_liquid,t.ebf_eating,t.ebf_no_bf_no_milk,t.ebf_no_bf_pregnant_again,t.ebf_no_bf_child_too_old,t.ebf_no_bf_mother_sick,t.cf_eligible,t.cf_in_month,t.cf_diet_diversity,t.cf_diet_quantity,t.cf_handwashing,t.cf_demo,t.fully_immunized_eligible,t.fully_immunized_on_time,t.fully_immunized_late,t.counsel_ebf,t.counsel_adequate_bf,t.counsel_pediatric_ifa,t.counsel_comp_feeding_vid,t.counsel_increase_food_bf,t.counsel_manage_breast_problems,t.counsel_skin_to_skin,t.counsel_immediate_breastfeeding,t.recorded_weight,t.recorded_height,t.has_aadhar_id,t.thr_eligible,t.pnc_eligible,t.cf_initiation_in_month,t.cf_initiation_eligible,t.height_measured_in_month,t.current_month_stunting,t.stunting_last_recorded,t.wasting_last_recorded,t.current_month_wasting,t.valid_in_month,t.valid_all_registered_in_month,t.ebf_no_info_recorded,t.dob,t.sex,t.age_tranche,t.caste,t.disabled,t.minority,t.resident,t.immunization_in_month,t.days_ration_given_child,t.zscore_grading_hfa,t.zscore_grading_hfa_recorded_in_month,t.zscore_grading_wfh,t.zscore_grading_wfh_recorded_in_month,t.muac_grading,ccs.case_id as ccs_record_case_id,t.date_death,awc.state_name,awc.district_name,awc.block_name,awc.awc_name,awc.awc_site_code FROM child_health_monthly t
            LEFT JOIN awc_location awc on t.awc_id=awc.doc_id and awc.supervisor_id=t.supervisor_id
            LEFT JOIN "ucr_icds-cas_static-person_cases_v3_2ae0879a" mother on mother.doc_id=t.mother_case_id
              AND awc.state_id = mother.state_id and mother.supervisor_id=t.supervisor_id
            LEFT JOIN "ccs_record_monthly" ccs on ccs.person_case_id=mother.doc_id AND ccs.add=t.dob
                AND (ccs.child_name is null OR ccs.child_name=t.person_name)
                AND ccs.month=t.month AND ccs.supervisor_id=t.supervisor_id
            WHERE awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175' AND awc.district_id='b4bf9bd9246d4bc495025e802eaaed0f' AND awc.block_id='0940c1ea4d7e48cf8c665d53bcf3a77e' AND t.month='2019-12-01'
        ) TO '/tmp/cas_data_export_dholi.csv' WITH CSV HEADER ENCODING 'UTF-8';




/*
 Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Nested Loop Left Join  (cost=62.77..66.88 rows=1 width=490)
               ->  Nested Loop Left Join  (cost=62.21..66.08 rows=1 width=550)
                     Join Filter: (awc.state_id = mother.state_id)
                     ->  Nested Loop  (cost=62.21..65.56 rows=1 width=583)
                           ->  Index Scan using awc_location_pkey_102840 on awc_location_102840 awc  (cost=0.68..2.90 rows=1 width=164)
                                 Index Cond: ((state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text) AND (district_id = 'b4bf9bd9246d4bc495025e802eaaed0f'::text) AND (block_id = '0940c1ea4d7e48cf8c665d53bcf3a77e'::text))
                           ->  Bitmap Heap Scan on child_health_monthly_102648 t  (cost=61.54..62.66 rows=1 width=482)
                                 Recheck Cond: ((awc_id = awc.doc_id) AND (month = '2019-12-01'::date) AND (supervisor_id = awc.supervisor_id))
                                 ->  BitmapAnd  (cost=61.54..61.54 rows=1 width=0)
                                       ->  Bitmap Index Scan on chm_awc_idx_102648  (cost=0.00..18.39 rows=1057 width=0)
                                             Index Cond: (awc_id = awc.doc_id)
                                       ->  Bitmap Index Scan on chm_month_supervisor_id_102648  (cost=0.00..42.90 rows=2254 width=0)
                                             Index Cond: ((month = '2019-12-01'::date) AND (supervisor_id = awc.supervisor_id))
                     ->  Index Scan using "ix_ucr_icds-cas_person_cases_v3_doc_id_hash_103866" on "ucr_icds-cas_static-person_cases_v3_2ae0879a_103866" mother  (cost=0.00..0.51 rows=1 width=103)
                           Index Cond: (doc_id = t.mother_case_id)
                           Filter: ((state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text) AND (supervisor_id = t.supervisor_id))
               ->  Index Scan using crm_person_add_case_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.55..0.79 rows=1 width=143)
                     Index Cond: ((person_case_id = mother.doc_id) AND (add = t.dob))
                     Filter: ((month = '2019-12-01'::date) AND ((child_name IS NULL) OR (child_name = t.person_name)) AND (month = t.month) AND (supervisor_id = t.supervisor_id))
(24 rows)

 */
