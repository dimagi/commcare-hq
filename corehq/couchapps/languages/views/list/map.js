function(doc) {
  if (doc.doc_type == "Application") {
    for (var lang in doc.langs) {
      emit([doc.domain, doc.langs[lang]], 1);
    }
  }
}
