function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id && !doc.closed) {
        emit([doc.domain, doc.user_id], {user_id: doc.user_id, active_cases: 1});
    }
}