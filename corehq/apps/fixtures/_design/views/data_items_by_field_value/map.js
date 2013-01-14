function (doc) {
    if (doc.doc_type === 'FixtureDataItem') {
        for (var key in doc.fields) {
            emit([doc.domain, doc.data_type_id, key, doc.fields[key]])
        }
    }
}