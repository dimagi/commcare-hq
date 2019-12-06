/*
Daily indicator for a particular date
 */

COPY(select state_name as "State", num_launched_awcs as "Total Anganwadis having ICDS CAS", daily_attendance_open as "Number of  anganwadis open", CASE WHEN num_launched_awcs>0 then round((daily_attendance_open/num_launched_awcs::float*100)::numeric,2) ELSE 0 END as "Percentage of anganwadis open", pse_eligible as "Total Number of Children eligible for PSE", total_attended_pse as "Total Number
of Children Attended PSE", CASE WHEN pse_eligible>0 then round((total_attended_pse/pse_eligible::float*100)::numeric,2) ELSE 0 END  as "Percentage of Children attended PSE" from daily_indicators where dat
e='2019-12-04' order by state_name) to STDOUT DELIMITER ',' CSV HEADER;
