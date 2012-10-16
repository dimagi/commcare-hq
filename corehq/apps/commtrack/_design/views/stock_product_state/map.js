function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point-product') {
	var leaf_location = doc.location_[doc.location_.length - 1];
	for (var i = 0; i < doc.actions.length; i++) {
	    var case_action = doc.actions[i];
	    emit([doc.domain, leaf_location, doc.product, case_action.server_date], case_action);
	}
    }
}
