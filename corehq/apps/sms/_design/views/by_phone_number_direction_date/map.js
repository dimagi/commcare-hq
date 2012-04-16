function(doc) {
    if (doc.base_doc == "MessageLog") {
    	emit([doc.doc_type, doc.phone_number, doc.direction, doc.date], null);
    }
}
