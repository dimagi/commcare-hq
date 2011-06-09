function(doc) { 
    if (doc.doc_type == "SyncLog") {
        emit([doc.chw_id, doc.date], 1);
    }
}