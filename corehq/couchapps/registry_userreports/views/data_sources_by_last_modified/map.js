function (doc) {
    if(doc.doc_type === "RegistryDataSourceConfiguration" && doc.is_deactivated == false) {
        emit([
            doc.last_modified,
            doc.domain,
        ], null);
    }
}
