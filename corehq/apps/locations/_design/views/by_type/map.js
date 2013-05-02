function(doc) {
    if (doc.doc_type == "Location") {
	var emit_ = function(loc_id) {
	    emit([doc.domain, doc.location_type, loc_id], null);
	}

	emit_(null);
	emit_(doc._id);
	for (var i = 0; i < doc.lineage.length; i++) {
	    emit_(doc.lineage[i]);
	}
    }
}
