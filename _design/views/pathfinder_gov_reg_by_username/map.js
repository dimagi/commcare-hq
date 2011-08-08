function(doc) {
  if (doc.doc_type == 'XFormInstance'
	&& doc.xmlns.indexOf('reg') != -1
) {
  var d = new Date(doc.form.patient.date_of_registration);
  emit([doc.domain, doc.form.meta.username], null);
}
}
