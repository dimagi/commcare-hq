function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id && !doc.closed) {
        emit([doc.domain, doc.user_id], 1);
    }
}