function(doc, req) {
    return doc.doc_type === 'Domain' && !doc.is_snapshot
}