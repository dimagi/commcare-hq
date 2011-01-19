function(doc) {
  if(doc.doc_type == "XFormInstance" && doc.form.meta.username) {
    emit([doc.domain, doc.form.meta.userID], null);
  }
}