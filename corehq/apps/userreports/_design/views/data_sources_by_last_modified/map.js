function (doc) {
    if(doc.doc_type === "DataSourceConfiguration" && doc.is_deactivated == false) {
        emit([
            doc.last_modified,
            doc.domain,
            doc._id,
        ], null);
    }
}
