function(doc) {
  if (doc.base_doc == "MessageLog") {
    	emit([doc.domain, doc.doc_type, doc.date], null);
    }
}
