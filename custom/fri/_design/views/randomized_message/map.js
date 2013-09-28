function(doc) {
    if(doc.doc_type === "FRIRandomizedMessage") {
        emit([doc.domain, doc.case_id, doc.order], null);
    }
}
