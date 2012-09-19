function(doc) {
  if (doc.doc_type == 'XFormInstance'

        && doc.xmlns == 'http://dev.commcarehq.org/Pathfinder/pathfinder_cc_followup')
{
  var d = new Date(doc.form.meta.timeStart);
  emit([doc.domain, doc.form.case.case_id, d.getUTCFullYear(), d.getUTCMonth()+1]);
}
}