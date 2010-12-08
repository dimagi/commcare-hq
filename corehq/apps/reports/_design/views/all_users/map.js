function(doc) {
  if(doc.doc_type == "XFormInstance" && doc.form.Meta.username) {
    emit([doc.domain, doc.form.Meta.username], null);
  }
}