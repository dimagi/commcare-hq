function(doc) { 
    if (doc.doc_type == "SyncLog") {
        emit([doc.user_id, doc.date, doc.last_seq], 1);
    }
}