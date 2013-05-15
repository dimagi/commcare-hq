function(doc) {
  if(doc.doc_type == "Application") {
    for (var i in doc.modules) {
      emit([doc.domain, doc.modules[i].case_type], null);
    }
  }
}
