function (doc) {
    if (doc.doc_type === "CaseReminderHandler") {
        emit([doc.domain, doc.case_type], null);
    }
}