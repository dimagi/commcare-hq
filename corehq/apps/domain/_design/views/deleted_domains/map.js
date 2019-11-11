function (doc) {
    if (doc.doc_type === "Domain-Deleted") {
        emit(doc.name, null);
    }
}
