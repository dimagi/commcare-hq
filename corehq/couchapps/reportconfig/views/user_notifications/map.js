function(doc) {
    if (doc.doc_type == "ReportNotification" || doc.doc_type == "WeeklyReportNotification" || doc.doc_type == "DailyReportNotification") {
        // after migrate_report_notifications has been run a second time, we can remove the checks for Weekly and DailyReportNotification
        emit([doc.domain, doc.owner_id], null);
    }
}
