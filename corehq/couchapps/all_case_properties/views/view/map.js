function (doc) {
    if (doc.doc_type === 'CommCareCase' && doc.type) {
        var actions = doc.actions;
        var i, k;
        for (i = 0; i < actions.length; i += 1) {
            if (actions[i].updated_known_properties) {
	            for (k in actions[i].updated_known_properties) {
	                if (actions[i].updated_known_properties.hasOwnProperty(k)) {
	                    emit([doc.domain, doc.type, k], null);   
	                }
	            }
            }
            if (actions[i].updated_unknown_properties) {
                for (k in actions[i].updated_unknown_properties) {
                    if (actions[i].updated_unknown_properties.hasOwnProperty(k)) {
                        emit([doc.domain, doc.type, k], null);   
                    }
                }
            }
        }
    }
}