function(doc) {
    if(doc.base_doc === "MobileBackend" && doc.backend_type === "SMS" && doc.is_global) {
        emit([doc.name], null);
    }
}
