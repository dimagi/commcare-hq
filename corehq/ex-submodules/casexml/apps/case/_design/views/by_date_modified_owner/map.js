function (doc) {
    if (doc.doc_type === "CommCareCase") {
        var date = doc.closed_on || doc.modified_on;
        var owner_id = doc.owner_id || doc.user_id;
        var closed_status = (doc.closed) ? "closed" : "open",
            emit_entry = {
                closed: doc.closed,
                type: doc.type
            };

        emit([doc.domain, closed_status, doc.type, owner_id, date], emit_entry);
        emit([doc.domain, closed_status, {}, owner_id, date], emit_entry);
        emit([doc.domain, {}, doc.type, owner_id, date], emit_entry);
        emit([doc.domain, {}, {}, owner_id, date], emit_entry);
    }
}