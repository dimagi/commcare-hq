function (doc) {
    if (doc.doc_type === 'StandaloneTranslationDoc') {
        emit([doc.domain, doc.area], null);
    }
}
