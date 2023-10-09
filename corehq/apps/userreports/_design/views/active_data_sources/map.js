function (doc) {
    if(doc.doc_type === "DataSourceConfiguration" && doc.is_deactivated == false) {
        emit([
            doc.domain,
            doc.table_id,
        ], null);
    }
}

// forcing view to be reindex - Graham Oct 4th 2023
