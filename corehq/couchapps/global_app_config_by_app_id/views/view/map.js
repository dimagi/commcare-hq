function(doc) {
    if (doc.doc_type == "GlobalAppConfig") {
        emit([doc.app_id, doc.domain], null);
    }
}
