function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point-product') {
        var leaf_location = doc.location_[doc.location_.length - 1];
        for (var i = 0; i < doc.actions.length; i++) {
            var case_action = doc.actions[i];
            emit([doc.domain, leaf_location, doc.product, case_action.server_date], case_action);
        }

        var emit_for_loc = function(loc, case_action) {
            emit([doc.domain, case_action.server_date, loc], [leaf_location, doc.product, case_action]);
        };
        for (var i = 0; i < doc.actions.length; i++) {
            var case_action = doc.actions[i];
            emit_for_loc(null, case_action);
            for (var j = 0; j < doc.location_.length; j++) {
                emit_for_loc(doc.location_[j], case_action);
            }
        }
    }
}
