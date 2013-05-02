function(doc) {
    if(doc.doc_type === "CommCareCase") {
        var user = doc.owner_id || doc.user_id,
            date = doc.closed_on || doc.modified_on,
            status = (doc.closed_on) ? "closed" : "open",
            case_type = doc.type || "";
        var entry = {};
        entry.owner_id = user;
        entry.user_id = doc.user_id;
        entry.type = case_type;
        emit(["", doc.domain, date, user], entry);
        emit(["user_first", doc.domain, user, date], entry);
        emit(["type", doc.domain, case_type, date, user], entry);
        emit(["status", doc.domain, status, date, user], entry);
        emit(["status type", doc.domain, status, case_type, date, user], entry);
    }
}