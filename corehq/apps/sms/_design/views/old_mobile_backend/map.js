function(doc) {
    if(doc.doc_type == "MobileBackend") {
        emit([doc.description], null);
    }
}
