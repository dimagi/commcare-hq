function(doc) {
  if(doc.doc_type == "XFormInstance") {
    emit([doc.domain, doc.form.Meta.username], null);
  }
}