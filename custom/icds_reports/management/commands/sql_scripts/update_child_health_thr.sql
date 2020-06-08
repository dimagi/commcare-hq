select SUM(CASE WHEN thr_eligible=1 THEN COALESCE(thr.days_ration_given_child, 0) ELSE 0 END)
from child_health_monthly inner join  awc_location ON (
      (child_health_monthly.supervisor_id = awc_location.supervisor_id) AND
      ("awc_location"."doc_id" = "child_health_monthly"."awc_id")
  )
left join icds_dashboard_child_health_thr_forms thr on
        (
        child_health_monthly.state_id= thr.state_id AND
        child_health_monthly.month = thr.month AND
        child_health_monthly.supervisor_id = thr.supervisor_id AND
        child_health_monthly.case_id = thr.case_id
        )
where child_health_monthly.month='2020-02-01' and state_is_test is distinct from 1
