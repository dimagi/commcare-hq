function (doc) {
    if(doc.doc_type === "ReportConfiguration") {
        emit(doc.domain, null);
    }
}
