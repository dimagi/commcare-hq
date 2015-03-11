function (doc) {
    if(doc.doc_type === "ReportConfiguration") {
        emit([doc.domain, doc.config_id], null);
    }
}
