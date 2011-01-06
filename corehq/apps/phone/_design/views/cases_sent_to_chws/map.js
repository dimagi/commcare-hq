function(doc) { 
    if (doc.doc_type == "SyncLog") {
        for (i in doc.cases) {
            emit([doc.chw_id, doc.cases[i]], new Date(doc.date));
        }
    }
}