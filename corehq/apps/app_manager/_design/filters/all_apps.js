function(doc, req) {
    return doc.doc_type === 'Application' || doc.doc_type === 'RemoteApp'
}
