function (doc) {
    if(doc.doc_type === "DataSourceConfiguration") {
        var source_id = null;
        var app_id = null;
        var app_version = null;
        if (doc.meta && doc.meta.build){
            source_id = doc.meta.build.source_id;
            app_id = doc.meta.build.app_id;
            app_version = doc.meta.build.app_version;
        }
        emit([
            doc.domain,
            doc.referenced_doc_type,
            source_id,
            app_id,
            app_version
        ], null);
    }
}
