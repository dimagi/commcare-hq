function (doc) {
    if (doc.doc_type === 'FixtureDataItem') {
        emit([doc.domain, doc.data_type_id, doc.sort_key], null);
    }
}
