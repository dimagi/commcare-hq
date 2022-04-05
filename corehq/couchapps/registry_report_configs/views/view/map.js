function (doc) {
    if(doc.doc_type === "RegistryReportConfiguration") {
        emit([doc.domain, doc.config_id], null);
    }
}
