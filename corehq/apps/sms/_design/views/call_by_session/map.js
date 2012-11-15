function(doc) {
    if (doc.doc_type == "CallLog") {
    	emit([doc.gateway_session_id, doc.date], null);
    }
}
