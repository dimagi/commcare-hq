function(doc) {
  if (doc.doc_type == 'XFormInstance'

        && doc.xmlns == 'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_followup')
{
  var d = new Date(doc.form.meta.timeStart);
  emit([doc.domain, doc.form.case.case_id], [doc.form.meta.username, doc.form.patient.reg_followup_hiv, doc.form.patient.type_of_client, doc.form.patient.referrals_hiv, doc.form.patient.ctc, d.getFullYear(), d.getMonth()]);
}
}