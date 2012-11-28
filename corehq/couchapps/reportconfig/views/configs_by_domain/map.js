function (doc) {
    if (doc.doc_type == "ReportConfig") {
        emit(["name slug", doc.domain, doc.owner_id, doc.report_slug, doc.name], null);
        emit(["name", doc.domain, doc.owner_id, doc.name, doc.report_slug], null);
    }
}
