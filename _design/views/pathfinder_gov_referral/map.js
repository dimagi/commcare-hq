function(doc) {
  if (doc.doc_type == 'XFormInstance'
        && doc.xmlns.indexOf('ref_resolv') != -1)
{
  emit([doc.form.case.case_id], null);
}
}