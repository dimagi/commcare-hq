function (doc) {
    if (doc.doc_type === "Product") {
        emit([doc.domain, doc.name], null);
    }
}