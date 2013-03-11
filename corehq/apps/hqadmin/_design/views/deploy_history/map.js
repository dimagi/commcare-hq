function (doc) {
    if (doc.doc_type === 'HqDeploy') {
        emit(doc.date, null);
    }
}