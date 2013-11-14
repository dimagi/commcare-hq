function (doc) {
    if (doc.doc_type === 'FixtureDataItem') {
        for (var key in doc.fields) {
            if (doc.fields.hasOwnProperty(key)) {
                    if (doc.fields[key].doc_type === 'FixtureFieldItem'){
                            emit([doc.domain, doc.data_type_id, key, doc.fields[key].field_value]);
                    }
                else {
                        emit([doc.domain, doc.data_type_id, key, doc.fields[key]]);
                }
            }
        }
    }
}