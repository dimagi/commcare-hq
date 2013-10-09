function(doc) {
    if(doc.doc_type == "VerifiedNumber") {
        emit([doc.domain, doc.owner_doc_type, doc.owner_id], null);
    }
}
