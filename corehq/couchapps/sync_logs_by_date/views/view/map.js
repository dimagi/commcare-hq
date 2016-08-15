function(doc) {
    if (doc.doc_type == "SyncLog") {
        emit([doc.date], 1);
    }
}
