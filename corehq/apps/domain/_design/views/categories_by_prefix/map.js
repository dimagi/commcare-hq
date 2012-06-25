function (doc) {
    if (doc.doc_type === "Domain" && doc.project_type) {
        emit(doc.project_type, null);
    }
}