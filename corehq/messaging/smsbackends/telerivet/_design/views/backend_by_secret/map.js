function(doc) {
    if(doc.base_doc === "MobileBackend" && doc.backend_type === "SMS" && doc.doc_type === "TelerivetBackend") {
        emit([doc.webhook_secret], null);
    }
}
