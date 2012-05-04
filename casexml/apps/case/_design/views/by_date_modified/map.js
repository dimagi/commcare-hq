function (doc) {
    if (doc.doc_type === "CommCareCase") {
        var date = doc.closed_on || doc.modified_on;
        emit([doc.domain, doc.closed, doc.type, doc.user_id, date], null);
        emit([doc.domain, doc.closed, {}, doc.user_id, date], null);
        emit([doc.domain, {}, doc.type, doc.user_id, date], null);
        emit([doc.domain, {}, {}, doc.user_id, date], null);
    }
}