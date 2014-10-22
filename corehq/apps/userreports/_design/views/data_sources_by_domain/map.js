function (doc) {
    if(doc.doc_type === "DataSourceConfiguration") {
        emit(doc.domain, null);
    }
}
