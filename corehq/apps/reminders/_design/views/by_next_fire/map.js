function (doc) {
    if (doc.doc_type === "CaseReminder" && doc.active && !doc.error) {
        // So you can find overdue reminders for a single domain
        emit([doc.domain, doc.next_fire], null);
        // So you can find all overdue reminders for irrespective of domain
        emit([null, doc.next_fire], null);
    }
}
