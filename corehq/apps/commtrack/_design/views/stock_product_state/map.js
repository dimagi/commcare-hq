function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point-product') {
	var location = null;
	for (var i = 0; i < doc.indices.length; i++) {
	    var case_index = doc.indices[i];
	    if (case_index.referenced_type == 'supply-point') {
		location = case_index.referenced_id;
		break;
	    }
	}

	for (var i = 0; i < doc.actions.length; i++) {
	    var case_action = doc.actions[i];
	    emit([doc.domain, location, doc.product, case_action.server_date], case_action);
	}
    }
}
