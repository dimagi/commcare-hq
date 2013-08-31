function (doc, req) {
    return (doc.doc_type && doc.doc_type === req.query.doc_type) 
}
