function(doc) {
    if (doc.doc_type === "FixtureReportResult") {
        emit([doc.domain, doc.location_id, doc.start_date, doc.end_date, doc.report_slug], null);
    }
}
