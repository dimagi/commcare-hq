function(doc){
    if (doc.doc_type === 'Application' && doc.copy_of === null && doc.anonymous_cloudcare_enabled) {
        emit([doc.domain, doc.anonymous_cloudcare_hash, doc._id], null);
    }
}

