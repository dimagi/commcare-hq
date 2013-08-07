function (doc) {
    if (doc.doc_type === "CommCareCase" && doc.user_id){
        var owner_id = doc.owner_id || doc.user_id
        var status = (doc.closed) ? "closed" : "open";

        emit([doc.domain, status, owner_id], 1);
    }
}