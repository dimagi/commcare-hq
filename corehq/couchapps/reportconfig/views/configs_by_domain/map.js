function (doc) {
    if (doc.doc_type == "ReportConfig") {
        emit(["by_name_with_slug", doc.domain, doc.owner_id, doc.report_slug, doc.name], null);
        emit(["by_name_no_slug", doc.domain, doc.owner_id, doc.name, doc.report_slug], null);
    }
}
