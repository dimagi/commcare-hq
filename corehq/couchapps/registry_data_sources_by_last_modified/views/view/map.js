function (doc) {
    if(doc.doc_type === "RegistryDataSourceConfiguration") {
        emit([
            doc.last_modified,
            doc.domain,
        ], null);
    }
}
