function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id) {
        var owner_id = doc.owner_id || doc.user_id;

        emit(["all", doc.domain, owner_id], 1);
        emit(["type", doc.domain, doc.type, owner_id], 1);

        var status = (doc.closed) ? "closed" : "open";
        emit([status, doc.domain, owner_id], 1);
        emit([status+" type", doc.domain, doc.type, owner_id], 1);
    }
}