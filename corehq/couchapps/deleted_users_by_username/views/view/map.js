function(doc) {
    if(doc.base_doc === "CouchUser-Deleted") {
        emit(doc.username, null);
    }
}
