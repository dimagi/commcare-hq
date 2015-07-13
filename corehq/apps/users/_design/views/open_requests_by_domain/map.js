function (doc) {
    if (doc.doc_type === "DomainRequest" && !doc.is_approved) {
        emit([doc.domain], null); 
    }
}
