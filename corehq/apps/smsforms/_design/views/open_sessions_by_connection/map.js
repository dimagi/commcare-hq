function(doc) {
    if(doc.doc_type == "XFormsSession") {
        if (!doc.end_time) {
            emit([doc.domain, doc.connection_id], null);
        }
    }
}
