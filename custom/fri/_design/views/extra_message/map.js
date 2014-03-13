function(doc) {
    if(doc.doc_type === "FRIExtraMessage") {
        emit([doc.domain, doc.message_id], null);
    }
}
