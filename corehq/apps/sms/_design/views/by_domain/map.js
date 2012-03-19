function(doc) {
  if (doc.base_doc == "MessageLog") {
    	emit([doc.doc_type, doc.domain, doc.date], null);
    }
}
