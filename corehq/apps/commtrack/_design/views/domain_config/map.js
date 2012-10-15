function (doc) {
    if (doc.doc_type === "CommtrackConfig") {
        emit([doc.domain], null);
    }
}