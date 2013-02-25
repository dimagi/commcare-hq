function (doc) {
    if (doc.doc_type === "CaseReminder" && doc.error) {
        emit([doc.domain, doc.next_fire], null);
    }
}
