function(doc) {
    if(doc.doc_type == "DailyReportNotification") {
        emit(doc.hours, null);
    }
}