function (doc) {
    if (doc.doc_type === "CommCareCase") {
        var date = doc.server_modified_on;
        var owner_id = doc.owner_id || doc.user_id;
        emit([doc.domain, owner_id, date], null);
    }
}
