function (doc) {
    if (doc.doc_type === 'FixtureDataType') {
        emit(doc.domain, null);
    }
}