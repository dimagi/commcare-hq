function(doc) {
    if(doc.doc_type === "CommCareCase") {
        var user = doc.owner_id || doc.user_id,
            date = doc.closed_on || doc.modified_on;
        var entry = {};
        entry.owner_id = user;
        entry.user_id = doc.user_id;
        entry.type = doc.type;
        emit(["", doc.domain, date, user], entry);
        emit(["type", doc.domain, doc.type, date, user], entry);
    }
}