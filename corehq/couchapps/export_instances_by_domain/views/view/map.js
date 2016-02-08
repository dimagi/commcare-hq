function(doc) {
    if (doc.doc_type === "FormExportInstance" || doc.doc_type === "CaseExportInstance") {
        emit([doc.domain, doc.doc_type, doc.is_deidentified], null);
    }
}
