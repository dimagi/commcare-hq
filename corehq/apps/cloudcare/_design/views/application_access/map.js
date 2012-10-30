function (doc) {
    if (doc.doc_type === 'ApplicationAccess') {
        emit(doc.domain, null);
    }
}