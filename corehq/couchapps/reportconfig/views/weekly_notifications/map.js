function(doc) {
    if (doc.doc_type == "WeeklyReportNotification" ||
        (doc.doc_type == "ReportNotification" && doc.day_of_week != -1))
    {
        emit([doc.day_of_week, doc.hours], null);
    }
}
