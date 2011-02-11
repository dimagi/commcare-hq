function(doc) {
    if(doc.doc_type == "WeeklyReportNotification") {
        emit([doc.day_of_week, doc.hours], null);
    }
}