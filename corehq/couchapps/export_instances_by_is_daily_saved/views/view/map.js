function(doc) {
    if (doc.doc_type === "FormExportInstance" || doc.doc_type === "CaseExportInstance") {
        emit([doc.is_daily_saved_export, doc.auto_rebuild_enabled, doc.last_accessed, doc.domain, doc.doc_type], null);
    }
}
