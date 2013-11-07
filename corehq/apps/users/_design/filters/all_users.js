function(doc, req) {
    return doc.base_doc === 'CouchUser' || doc.base_doc === 'CouchUser-Deleted'
}
