function (doc) {
    if(doc.doc_type === "PerformanceConfiguration") {
        emit(doc.domain, null);
    }
}
