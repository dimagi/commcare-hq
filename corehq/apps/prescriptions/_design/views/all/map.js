function (doc) {
    if (doc.doc_type === 'Prescription') {
        emit([doc.type, doc.domain, doc.end], null);
    }
}