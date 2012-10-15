function (doc) {
    if (doc.doc_type === "Deployment") {
        emit(doc.domain_id, null);
    }
}