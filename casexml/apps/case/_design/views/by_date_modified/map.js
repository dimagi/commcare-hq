function (doc) {
    if (doc.doc_type === "CommCareCase") {
        var date = doc.closed_on || doc.modified_on,
            emit_entry = {
                closed: doc.closed,
                type: doc.type
            };
        emit([doc.domain, doc.closed, doc.type, doc.user_id, date], emit_entry);
        emit([doc.domain, doc.closed, {}, doc.user_id, date], emit_entry);
        emit([doc.domain, {}, doc.type, doc.user_id, date], emit_entry);
        emit([doc.domain, {}, {}, doc.user_id, date], emit_entry);
    }
}