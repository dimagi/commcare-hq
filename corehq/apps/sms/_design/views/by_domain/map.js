function(doc) {
  if (doc.doc_type == "MessageLog") {
    	emit([doc.domain, doc.date], null);
    }
}