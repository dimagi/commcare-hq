function(doc) {
    if (doc.doc_type === "ExpectedCallbackEventLog") {
    	emit([doc.domain, doc.date, doc.couch_recipient], null);
    }
}
