function(doc) {
    if (doc.doc_type == "DailyReportNotification" || 
        (doc.doc_type == "ReportNotification" && doc.day_of_week == -1))
    {
        emit(doc.hours, null);
    }
}
