DROP TABLE IF EXISTS temp_ccs_table;
CREATE TABLE temp_ccs_table
  AS (
  SELECT
    ccs.case_id as case_id,
    ccs.month as month,
    ccs.supervisor_id as supervisor_id,
    case_list.complication_type as complication_type,
    agg_bp.reason_no_ifa as reason_no_ifa,
    agg_bp.new_ifa_tablets_total as new_ifa_tablets_total_bp,
    agg_pnc.new_ifa_tablets_total as new_ifa_tablets_total_pnc,
    agg_bp.ifa_last_seven_days as ifa_last_seven_days
    FROM "ccs_record_monthly" ccs
    LEFT OUTER JOIN "awc_location" awc ON ccs.awc_id = awc.doc_id AND awc.supervisor_id = ccs.supervisor_id
    LEFT OUtER JOIN "ucr_icds-cas_static-ccs_record_cases_cedcca39" case_list ON ccs.case_id = case_list.doc_id AND case_list.supervisor_id = ccs.supervisor_id
    LEFT OUTER JOIN "icds_dashboard_ccs_record_bp_forms" agg_bp ON ccs.case_id = agg_bp.case_id AND agg_bp.month = ccs.month AND ccs.supervisor_id = agg_bp.supervisor_id
    LEFT OUTER JOIN "icds_dashboard_ccs_record_postnatal_forms" agg_pnc ON ccs.case_id = agg_pnc.case_id AND agg_pnc.month = ccs.month AND ccs.supervisor_id = agg_pnc.supervisor_id
    WHERE ccs.month='{month}'::date AND awc.state_id='{state_id}'
  );
SELECT create_distributed_table('temp_ccs_table', 'supervisor_id');
UPDATE "ccs_record_monthly" ccs
SET
    complication_type = ut.complication_type,
    reason_no_ifa = ut.reason_no_ifa,
    new_ifa_tablets_total_bp = ut.new_ifa_tablets_total_bp,
    new_ifa_tablets_total_pnc = ut.new_ifa_tablets_total_pnc,
    ifa_last_seven_days = ut.ifa_last_seven_days
FROM temp_ccs_table ut
WHERE (
    ccs.case_id = ut.case_id AND
    ccs.month = ut.month AND
    ccs.supervisor_id = ut.supervisor_id AND
    ccs.month = '{month}'
);
DROP TABLE IF EXISTS temp_ccs_table

