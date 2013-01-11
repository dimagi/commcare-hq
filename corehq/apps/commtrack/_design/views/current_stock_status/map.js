function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point-product' && doc.actions.length > 0) {
        var leaf_location = doc.location_[doc.location_.length - 1];
        emit([doc.domain, leaf_location, doc.product, doc.server_modified_on], 
             {
                _id: doc._id,
                stocked_out_since: doc.stocked_out_since,
                current_stock: doc.current_stock,
                location_: doc.location_,
                product: doc.product,
                server_modified_on: doc.server_modified_on
             }
        );
    }
}
