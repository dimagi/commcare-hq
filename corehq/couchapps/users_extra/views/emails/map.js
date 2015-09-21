function (doc) {
    if (doc.doc_type === 'WebUser') {
        emit(doc.username, null);
    }
}
