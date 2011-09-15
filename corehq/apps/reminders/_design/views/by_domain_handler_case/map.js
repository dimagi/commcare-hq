function (doc) {
    if (doc.doc_type === "CaseReminder") {
        emit([doc.domain, doc.handler_id, doc.case_id], null);
    }
}