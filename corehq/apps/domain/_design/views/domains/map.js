function (doc) {
    if (doc.doc_type === "Domain") {
        emit(doc.name, null);
    }
}