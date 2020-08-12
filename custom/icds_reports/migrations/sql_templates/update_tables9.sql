ALTER TABLE agg_awc ADD COLUMN num_launched_states integer;
ALTER TABLE agg_awc ADD COLUMN num_launched_districts integer;
ALTER TABLE agg_awc ADD COLUMN num_launched_blocks integer;
ALTER TABLE agg_awc ADD COLUMN num_launched_supervisors integer;
ALTER TABLE agg_awc ADD COLUMN num_launched_awcs integer;
ALTER TABLE agg_awc ADD COLUMN cases_household integer;
ALTER TABLE agg_awc ADD COLUMN cases_person integer;
ALTER TABLE agg_awc ADD COLUMN cases_person_all integer;
ALTER TABLE agg_awc ADD COLUMN cases_person_has_aadhaar integer;
ALTER TABLE agg_awc ADD COLUMN cases_ccs_pregnant_all integer;
ALTER TABLE agg_awc ADD COLUMN cases_ccs_lactating_all integer;
ALTER TABLE agg_awc ADD COLUMN cases_child_health_all integer;
ALTER TABLE agg_awc ADD COLUMN cases_person_adolescent_girls_11_14 integer;
ALTER TABLE agg_awc ADD COLUMN cases_person_adolescent_girls_15_18 integer;
ALTER TABLE agg_awc ADD COLUMN cases_person_adolescent_girls_11_14_all integer;
ALTER TABLE agg_awc ADD COLUMN cases_person_adolescent_girls_15_18_all integer;
ALTER TABLE agg_awc ADD COLUMN infra_infant_weighing_scale integer;

ALTER TABLE agg_child_health ADD COLUMN pnc_eligible integer;
ALTER TABLE agg_child_health ADD COLUMN height_eligible integer;
ALTER TABLE agg_child_health ADD COLUMN wasting_moderate integer;
ALTER TABLE agg_child_health ADD COLUMN wasting_severe integer;
ALTER TABLE agg_child_health ADD COLUMN stunting_moderate integer;
ALTER TABLE agg_child_health ADD COLUMN stunting_severe integer;
ALTER TABLE agg_child_health ADD COLUMN cf_initiation_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN cf_initiation_eligible integer;
ALTER TABLE agg_child_health ADD COLUMN height_measured_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN wasting_normal integer;
ALTER TABLE agg_child_health ADD COLUMN stunting_normal integer;
ALTER TABLE agg_child_health ADD COLUMN valid_all_registered_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN ebf_no_info_recorded integer;

ALTER TABLE child_health_monthly ADD COLUMN cf_initiation_in_month integer;
ALTER TABLE child_health_monthly ADD COLUMN cf_initiation_eligible integer;
ALTER TABLE child_health_monthly ADD COLUMN height_measured_in_month integer;
ALTER TABLE child_health_monthly ADD COLUMN current_month_stunting text;
ALTER TABLE child_health_monthly ADD COLUMN stunting_last_recorded text;
ALTER TABLE child_health_monthly ADD COLUMN wasting_last_recorded text;
ALTER TABLE child_health_monthly ADD COLUMN current_month_wasting text;
ALTER TABLE child_health_monthly ADD COLUMN valid_in_month integer;
ALTER TABLE child_health_monthly ADD COLUMN valid_all_registered_in_month integer;
ALTER TABLE child_health_monthly ADD COLUMN ebf_no_info_recorded integer;

ALTER TABLE agg_ccs_record ADD COLUMN valid_all_registered_in_month integer;
ALTER TABLE agg_ccs_record ADD COLUMN institutional_delivery_in_month integer;
ALTER TABLE agg_ccs_record ADD COLUMN lactating_all integer;
ALTER TABLE agg_ccs_record ADD COLUMN pregnant_all integer;

ALTER TABLE ccs_record_monthly ADD COLUMN pregnant integer;
ALTER TABLE ccs_record_monthly ADD COLUMN pregnant_all integer;
ALTER TABLE ccs_record_monthly ADD COLUMN lactating integer;
ALTER TABLE ccs_record_monthly ADD COLUMN lactating_all integer;
ALTER TABLE ccs_record_monthly ADD COLUMN institutional_delivery_in_month integer;




