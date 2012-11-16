function(doc) {
    if (doc.doc_type == "ReportNotification" || doc.doc_type == "WeeklyReportNotification" || doc.doc_type == "DailyReportNotification") {
        var owner_id;
        if (doc.user_ids) {
            // old doc
            owner_id = doc.user_ids[0];
        } else {
            owner_id = doc.owner_id;
        }
        emit([doc.domain, owner_id], null);
    }
}
