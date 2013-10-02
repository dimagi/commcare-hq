function (doc) {
    if (doc.doc_type === "CaseReminderHandler") {
        emit([doc.domain, doc.reminder_type, doc.start_datetime], null);
    }
}