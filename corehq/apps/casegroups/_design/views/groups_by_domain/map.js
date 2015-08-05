function (doc) {
    if (doc.doc_type === "CommCareCaseGroup") {
        emit([doc.domain, doc.name], null);
    }
}
