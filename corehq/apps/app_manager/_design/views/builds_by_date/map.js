function (doc) {
    if ((doc.doc_type === 'Application' || doc.doc_type === 'LinkedApplication') && doc.copy_of !== null) {
        emit(doc.built_on, null);
    }
}