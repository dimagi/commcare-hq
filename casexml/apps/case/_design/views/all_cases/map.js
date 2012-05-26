function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id) {
        emit(["all", doc.domain, doc.user_id], 1);
        emit(["type", doc.domain, doc.type, doc.user_id], 1);

        var status = (doc.closed) ? "closed" : "open";
        emit([status, doc.domain, doc.user_id], 1);
        emit([status+" type", doc.domain, doc.type, doc.user_id], 1);
    }
}