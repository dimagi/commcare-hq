function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point-product') {
        var emit_for_loc = function(loc) {
            emit([doc.domain, loc, doc.product], null);
        };
        emit_for_loc(null);
        for (var i = 0; i < doc.location_.length; i++) {
            emit_for_loc(doc.location_[i]);
        }
    }
}