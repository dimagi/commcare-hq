function (doc) {
    if (doc.doc_type === 'HqDeploy') {
        emit([doc.environment, doc.date], null);
    }
}