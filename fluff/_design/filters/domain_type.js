function (doc, req) {
    return (
        (!req.params.domain || doc.domain === req.params.domain) &&
        (!req.params.doc_type || doc.doc_type === req.params.doc_type)
    );
}