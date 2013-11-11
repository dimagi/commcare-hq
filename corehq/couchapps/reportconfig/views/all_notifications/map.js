function(doc) {
    if (doc.doc_type == "ReportNotification")
    {
        emit([doc.interval, doc.hour, doc.day], null);
    }
}
