function (doc) {
    if (doc.doc_type === "CaseReminder" && doc.active) {
        emit(doc.next_fire, null);
    }
}