function(doc) {
  if (doc.doc_type == "MessageLog") {
    	emit([doc.domain, doc.direction, doc.date], null);
    }
}