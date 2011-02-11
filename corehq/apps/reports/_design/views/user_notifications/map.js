function(doc) {
    if(doc.doc_type == "WeeklyReportNotification" || doc.doc_type == "DailyReportNotification") {
        for (i in doc.user_ids) {
            emit(doc.user_ids[i], null);
        }
    }
}