function(doc) {
    if(doc.doc_type === "XFormsSession") {
        if (!doc.end_time && (!doc.session_type || doc.session_type === "SMS")) {
            emit([doc.domain, doc.connection_id], null);
        }
    }
}
