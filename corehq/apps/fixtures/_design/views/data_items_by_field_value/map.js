function (doc) {
    if (doc.doc_type === 'FixtureDataItem') {
        for (var key in doc.fields) {
            if (doc.fields.hasOwnProperty(key)) {
                if (doc.fields[key] && doc.fields[key].doc_type === 'FieldList'){
                    for (var field_for_attribute in doc.fields[key].field_list){
                        var field = doc.fields[key].field_list[field_for_attribute];
                        emit([doc.domain, doc.data_type_id, key, field.field_value]);
                    }
                }
                else {
                    emit([doc.domain, doc.data_type_id, key, doc.fields[key]]);
                }
            }
        }
    }
}