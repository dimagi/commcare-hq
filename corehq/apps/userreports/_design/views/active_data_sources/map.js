function (doc) {
    if(doc.doc_type === "DataSourceConfiguration" && doc.is_deactivated == false) {
        emit([
            doc.domain,
            doc._id,
            doc.table_id,
        ], null);
    }
}