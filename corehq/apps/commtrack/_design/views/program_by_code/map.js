function (doc) {
    if (doc.doc_type === "Program") {
        emit([doc.domain, doc.code], null);
    }
}