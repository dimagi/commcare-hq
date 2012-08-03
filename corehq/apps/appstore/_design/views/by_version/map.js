function (doc) {
    if (doc.doc_type === 'Review') {
        emit([doc.domain, doc.user], doc.rating || 0);
    }
}