function(doc) { 
    if (doc.doc_type == "SyncLog") {
        emit([doc.user_id, doc.date], 1);
    }
}