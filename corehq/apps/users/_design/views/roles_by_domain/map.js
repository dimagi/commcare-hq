function (doc) {
    if (doc.doc_type === 'UserRole') {
        emit(doc.domain, null);
    }
}