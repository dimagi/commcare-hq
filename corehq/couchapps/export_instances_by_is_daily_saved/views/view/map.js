function(doc) {
    if (doc.doc_type === "FormExportInstance" || doc.doc_type === "CaseExportInstance") {
        emit([doc.is_daily_saved_export, doc.domain, doc.doc_type], null);
    }
}
