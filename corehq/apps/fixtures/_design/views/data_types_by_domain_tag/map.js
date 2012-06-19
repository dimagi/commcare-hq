function (doc) {
    if (doc.doc_type === 'FixtureDataType') {
        emit([doc.domain, doc.tag], null);
    }
}