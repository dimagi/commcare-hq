function(doc) {
    if(doc.doc_type == "CaseReminderEvent") {
        emit(doc.handler_id, doc);
    }
}
