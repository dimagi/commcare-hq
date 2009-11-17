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
   

/* take 2 at data by mobile healthcare worker.  Not for the weak of heart */

select all_records.username as 'Healthcare Worker',
       all_records.cnt as '# of Patients',
       if (hi_risk.cnt is null, 0, hi_risk.cnt) as '# of High Risk',
#       follows.cnt as '# of Follow Up',
       if(follows.cnt is null,0,follows.cnt) as '# of Follow Up',
       if(hi_risk_follows.cnt is null, 0, hi_risk_follows.cnt) as '# High Risk Receiving Follow Up',
       if(hi_risk_nofollows.cnt is null, 0, hi_risk_nofollows.cnt) as '# High Risk Needing Follow Up'
from
(select username, count(*) as cnt from
(
/* ##### begin duplicate table definition ######## */
select meta.username, meta.attachment_id,
       annotation_counts.cnt as follow_ups, reg.sampledata_hi_risk
from xformmanager_metadata meta
left outer join receiver_attachment attach
on attach.id = meta.attachment_id
left outer join (
  select attachment_id, count(*) as cnt from receiver_annotation
  group by attachment_id) annotation_counts
on attach.id = annotation_counts.attachment_id
left outer join schema_intel_grameen_safe_motherhood_registration_v0_3 reg
on meta.raw_data = reg.id
where meta.formdefmodel_id = 52
/* ##### end duplicate table definition ######## */
)
all_reg group by username) all_records
left outer join
(select username, count(*) as cnt from
(
/* ##### begin duplicate table definition ######## */
select meta.username, meta.attachment_id,
       annotation_counts.cnt as follow_ups, reg.sampledata_hi_risk
from xformmanager_metadata meta
left outer join receiver_attachment attach
on attach.id = meta.attachment_id
left outer join (
  select attachment_id, count(*) as cnt from receiver_annotation
  group by attachment_id) annotation_counts
on attach.id = annotation_counts.attachment_id
left outer join schema_intel_grameen_safe_motherhood_registration_v0_3 reg
on meta.raw_data = reg.id
where meta.formdefmodel_id = 52
/* ##### end duplicate table definition ######## */
)
all_reg
 where sampledata_hi_risk = 'yes'
 group by username) hi_risk
on all_records.username = hi_risk.username
left outer join
(select username, count(*) as cnt from
(
/* ##### begin duplicate table definition ######## */
select meta.username, meta.attachment_id,
       annotation_counts.cnt as follow_ups, reg.sampledata_hi_risk
from xformmanager_metadata meta
left outer join receiver_attachment attach
on attach.id = meta.attachment_id
left outer join (
  select attachment_id, count(*) as cnt from receiver_annotation
  group by attachment_id) annotation_counts
on attach.id = annotation_counts.attachment_id
left outer join schema_intel_grameen_safe_motherhood_registration_v0_3 reg
on meta.raw_data = reg.id
where meta.formdefmodel_id = 52
/* ##### end duplicate table definition ######## */
)
all_reg
 where follow_ups > 0 group by username) follows
on all_records.username = follows.username
left outer join
(select username, count(*) as cnt from
(
/* ##### begin duplicate table definition ######## */
select meta.username, meta.attachment_id,
       annotation_counts.cnt as follow_ups, reg.sampledata_hi_risk
from xformmanager_metadata meta
left outer join receiver_attachment attach
on attach.id = meta.attachment_id
left outer join (
  select attachment_id, count(*) as cnt from receiver_annotation
  group by attachment_id) annotation_counts
on attach.id = annotation_counts.attachment_id
left outer join schema_intel_grameen_safe_motherhood_registration_v0_3 reg
on meta.raw_data = reg.id
where meta.formdefmodel_id = 52
/* ##### end duplicate table definition ######## */
)
all_reg
 where follow_ups > 0 and sampledata_hi_risk = 'yes'
 group by username) hi_risk_follows
on all_records.username = hi_risk_follows.username

left outer join
(select username, count(*) as cnt from
(
/* ##### begin duplicate table definition ######## */
select meta.username, meta.attachment_id,
       annotation_counts.cnt as follow_ups, reg.sampledata_hi_risk
from xformmanager_metadata meta
left outer join receiver_attachment attach
on attach.id = meta.attachment_id
left outer join (
  select attachment_id, count(*) as cnt from receiver_annotation
  group by attachment_id) annotation_counts
on attach.id = annotation_counts.attachment_id
left outer join schema_intel_grameen_safe_motherhood_registration_v0_3 reg
on meta.raw_data = reg.id
where meta.formdefmodel_id = 52
/* ##### end duplicate table definition ######## */
)
all_reg
 where follow_ups = 0 or follow_ups is null and sampledata_hi_risk = 'yes'
 group by username) hi_risk_nofollows
on all_records.username = hi_risk_nofollows.username;


  
/* individual chw view */
SELECT sampledata_case_id as 'ID',
       meta_username as 'Healthcare Worker',
       sampledata_mother_name as 'Mother Name', 
       sampledata_address as 'Address',
       sampledata_hi_risk as 'Hi Risk?',
       id as 'row_id',
       'No' as 'Follow up?' /* need to fix this when we actually have FU */
FROM schema_intel_grameen_safe_motherhood_registration_v0_3
{{whereclause}}