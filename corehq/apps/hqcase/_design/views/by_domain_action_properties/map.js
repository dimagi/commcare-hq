function (doc) {
    if (doc.doc_type === 'CommCareCase' && doc.type) {
        var actions = doc.actions;
        for (var i = 0; i < actions.length; i += 1) {
            var fields = {};
            fields['known'] = actions[i]['updated_known_properties'];
            fields['unknown'] = actions[i]['updated_unknown_properties'];
            emit(doc.domain, fields);
        }
    }
}