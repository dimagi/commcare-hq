function(doc) {
    if (doc.base_doc == "MessageLog") {
    	emit([doc.couch_recipient_doc_type, doc.couch_recipient, doc.doc_type, doc.direction, doc.date], null);
    }
}
