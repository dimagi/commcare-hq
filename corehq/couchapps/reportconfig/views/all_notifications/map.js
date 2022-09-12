function(doc) {
    if (doc.doc_type == "ReportNotification")
    {
        emit([doc.interval, doc.hour, doc.minute, doc.day], {
            hour: doc.hour,
            stop_hour: doc.stop_hour
        });
    }
}
