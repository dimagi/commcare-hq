function(doc) {
    if(doc.base_doc === "CouchUser") {
        emit(doc.username, null);
    }
}