function (doc) {
    if (doc.doc_type == "ReportConfig") {
        emit([doc.domain, doc.owner_id, doc.report_slug], null);
    }
}
