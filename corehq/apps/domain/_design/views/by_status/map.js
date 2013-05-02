function (doc) {
    if (doc.doc_type === "Domain") {
        emit([doc.is_active, doc.name], null);
    }
}