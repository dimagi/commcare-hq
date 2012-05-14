function(doc) {
    if(doc.doc_type == "XFormsSession") {
        emit([doc.session_id, doc.modified_time], null);
    }
}
