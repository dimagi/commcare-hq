/* this file is for keeping readable versions of the sql reports in 
   source control, for ease of use */
   
   
 /* Intel/Grameen Data by Mobile Health worker */
 
select cases.meta_username as 'Healthcare Worker',
       cases.cnt as '# of Patients',
       hi_risk.cnt as '# of High Risk',
       followups.cnt as '# of Follow Up'
from (
  SELECT meta_username, count(distinct sampledata_case_id) as cnt
  FROM schema_intel_grameen_safe_motherhood_registration_v0_3
  group by meta_username
) cases left outer join
(
  select meta_username, count(*) as cnt
  from (
     select meta_username, sampledata_case_id
     from schema_intel_grameen_safe_motherhood_registration_v0_3
     where sampledata_hi_risk = 'yes'
     group by meta_username, sampledata_case_id
  ) hi_risk_cases
  group by meta_username
) hi_risk
  on cases.meta_username = hi_risk.meta_username
  left outer join
(  select meta_username, count(*) as cnt
   from schema_intel_grameen_safe_motherhood_followup_v0_2
   group by meta_username
) followups
on followups.meta_username = hi_risk.meta_username;
   
  
/* individual chw view */
SELECT sampledata_case_id as 'ID',
       meta_username as 'Healthcare Worker',
       sampledata_address as 'Address',
       sampledata_hi_risk as 'Hi Risk?',
       'No' as 'Follow up?' /* need to fix this when we actually have FU */
FROM schema_intel_grameen_safe_motherhood_registration_v0_3
{{whereclause}}