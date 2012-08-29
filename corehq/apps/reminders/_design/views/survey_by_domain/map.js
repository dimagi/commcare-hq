function (doc) {
    if (doc.doc_type === "Survey") {
        emit([doc.domain, doc.name], null);
    }
}
