function (doc) {
    if (doc.doc_type === 'Application' && doc.copy_of !== null) {
        emit(doc.built_on, null);
    }
}