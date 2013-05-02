function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id && !doc.closed) {
        emit([doc.domain, doc.type, doc.user_id], null);
        emit([doc.domain, doc.type, {}], null);
        emit([doc.domain, {}, doc.user_id], null);
        emit([doc.domain, {}, {}], null);
    }
}