function (doc) {
    if (doc.doc_type === 'HqDeploy') {
        emit(doc.date, {date: doc.date, user: doc.user});
    }
}