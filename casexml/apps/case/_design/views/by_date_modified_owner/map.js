function (doc) {
    if (doc.doc_type === "CommCareCase") {
        var date = doc.closed_on || doc.modified_on;
        var owner_id = doc.owner_id || doc.user_id;
        emit([doc.domain, doc.closed, doc.type, owner_id, date], null);
        emit([doc.domain, doc.closed, {}, owner_id, date], null);
        emit([doc.domain, {}, doc.type, owner_id, date], null);
        emit([doc.domain, {}, {}, owner_id, date], null);
    }
}