DELETE FROM "icds_dashboard_ccs_record_bp_forms" WHERE state_id = '{state_id}' AND month = '2020-03-01';
INSERT INTO "icds_dashboard_ccs_record_bp_forms" (
          case_id, supervisor_id, state_id, month, latest_time_end_processed,
          immediate_breastfeeding, play_birth_preparedness_vid, counsel_preparation, play_family_planning_vid,
          conceive, counsel_accessible_ppfp, eating_extra, resting, anc_weight, anc_blood_pressure, bp_sys, bp_dia,
          anc_hemoglobin, bleeding, swelling, blurred_vision, convulsions, rupture, anemia, anc_abnormalities,
          using_ifa, ifa_last_seven_days, reason_no_ifa, new_ifa_tablets_total, valid_visits
        ) (

          SELECT DISTINCT ccs_record_case_id AS case_id,
        supervisor_id,
        '{state_id}' as state_id,
        '2020-03-01'::date as month,
        LAST_VALUE(timeend) OVER w AS latest_time_end_processed,
        MAX(immediate_breastfeeding) OVER w AS immediate_breastfeeding,
        MAX(play_birth_preparedness_vid) OVER w as play_birth_preparedness_vid,
        MAX(counsel_preparation) OVER w as counsel_preparation,
        MAX(play_family_planning_vid) OVER w as play_family_planning_vid,
        MAX(conceive) OVER w as conceive,
        MAX(counsel_accessible_ppfp) OVER w as counsel_accessible_ppfp,
        LAST_VALUE(eating_extra) OVER w as eating_extra,
        LAST_VALUE(resting) OVER w as resting,
        LAST_VALUE(anc_weight) OVER w as anc_weight,
        LAST_VALUE(anc_blood_pressure) OVER w as anc_blood_pressure,
        LAST_VALUE(bp_sys) OVER w as bp_sys,
        LAST_VALUE(bp_dia) OVER w as bp_dia,
        LAST_VALUE(anc_hemoglobin) OVER w as anc_hemoglobin,
        LAST_VALUE(bleeding) OVER w as bleeding,
        LAST_VALUE(swelling) OVER w as swelling,
        LAST_VALUE(blurred_vision) OVER w as blurred_vision,
        LAST_VALUE(convulsions) OVER w as convulsions,
        LAST_VALUE(rupture) OVER w as rupture,
        LAST_VALUE(anemia) OVER w as anemia,
        LAST_VALUE(anc_abnormalities) OVER w as anc_abnormalities,
        LAST_VALUE(using_ifa) OVER w as using_ifa,
        GREATEST(LAST_VALUE(ifa_last_seven_days) OVER w, 0) as ifa_last_seven_days,
        LAST_VALUE(reason_no_ifa) OVER w as reason_no_ifa,
        GREATEST(LAST_VALUE(new_ifa_tablets_total) OVER w, 0) as new_ifa_tablets_total,
        SUM(CASE WHEN
            (unscheduled_visit=0 AND days_visit_late < 8) OR (timeend::DATE - next_visit) < 8
            THEN 1 ELSE 0 END
        ) OVER w as valid_visits
        FROM "ucr_icds-cas_static-dashboard_birth_prepa_e3e359ff"
        WHERE timeend < '2020-04-01' AND state_id = '{state_id}'
        WINDOW w AS (
            PARTITION BY supervisor_id, ccs_record_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        )
