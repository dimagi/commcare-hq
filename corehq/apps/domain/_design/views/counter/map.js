function (doc) {
    if (doc.doc_type === "DomainCounter") {
        emit([doc.domain, doc.name], null);
    }
}
