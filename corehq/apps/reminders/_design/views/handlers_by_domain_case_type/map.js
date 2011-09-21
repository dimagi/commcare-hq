function (doc) {
    if (doc.doc_type === "CaseReminderHandler") {
        emit([doc.domain, doc.case_type, doc.nickname], null);
    }
}