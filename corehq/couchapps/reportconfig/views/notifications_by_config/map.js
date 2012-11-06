function(doc) {
    if (doc.doc_type == "WeeklyReportNotification" || doc.doc_type == "DailyReportNotification") {
        if (doc.config_ids) {
            for (var i = 0; i < doc.config_ids.length; i++) {
                emit(doc.config_ids[i], null); 
            }
        }
    }
}
