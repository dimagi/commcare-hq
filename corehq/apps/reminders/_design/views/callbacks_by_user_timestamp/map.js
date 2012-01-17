function(doc) {
    if(doc.doc_type == "CaseReminderCallback") {
        emit([doc.user_id, doc.timestamp], null);
    }
}
