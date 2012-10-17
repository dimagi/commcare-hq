function(doc) {
    var emit_for_loc = function(loc) {
	emit([doc.domain, loc, doc.received_on], null);
    };

    if (doc.doc_type == "HQSubmission" && doc.xmlns == 'http://openrosa.org/commtrack/stock_report') {
	emit_for_loc(null);
	for (var i = 0; i < doc.location_.length; i++) {
	    emit_for_loc(doc.location_[i]);
	}
    }
}
