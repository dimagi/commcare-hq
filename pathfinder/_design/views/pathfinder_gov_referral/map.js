function(doc) {
  if (doc.doc_type == 'XFormInstance'
        && doc.xmlns.indexOf('ref_resolv') != -1)
{
    var d = new Date(doc.form.meta.timeEnd);

  emit([doc.form.case.case_id, d.getFullYear(), d.getMonth()+1], null);
}
}