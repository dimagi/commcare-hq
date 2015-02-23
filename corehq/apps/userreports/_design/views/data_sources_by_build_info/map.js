function (doc) {
    if(doc.doc_type === "DataSourceConfiguration") {
        // TODO: Do I need to check for existence of these properties?
        // TODO: Can I get rid of data sources by domain and just use this view?
        emit([
            doc.domain,
            doc.referenced_doc_type,
            doc.meta.build.source_id,
            doc.meta.build.app_id,
            doc.meta.build.app_version
        ], null);
    }
}
