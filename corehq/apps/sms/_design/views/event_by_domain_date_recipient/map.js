function(doc) {
    if (doc.doc_type == "EventLog") {
    	emit([doc.domain, doc.date, doc.couch_recipient_doc_type, doc.couch_recipient], null);
    }
}
