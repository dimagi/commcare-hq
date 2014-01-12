function (doc) {
    if (doc.doc_type === "Product") {
        emit([doc.domain, doc.program_id], null);
    }
}