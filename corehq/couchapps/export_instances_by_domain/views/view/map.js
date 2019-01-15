function(doc) {
    if (doc.doc_type === "FormExportInstance" || doc.doc_type === "CaseExportInstance") {
        emit([doc.domain, doc.doc_type, doc.is_deidentified, doc.is_daily_saved_export, doc.export_format, doc.name], null);
    }
}
