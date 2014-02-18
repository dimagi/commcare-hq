function(doc) {
    // broken, needs update
    if (doc.doc_type == "CommCareCase" && doc.type == 'commtrack-requisition') {
        var leafLocation = doc.location_[doc.location_.length - 1];
        var getSupplyPointProductCaseId = function (doc) {
            for (var i = 0; i < doc.indices.length; i++) {
                if (doc.indices[i].identifier === 'parent') {
                    return doc.indices[i].referenced_id;
                }
            }
        }
        var sppId = getSupplyPointProductCaseId(doc);
        if (sppId) {
            if (!doc.closed) {
                emit([doc.domain, leafLocation, 'open', sppId, doc.server_modified_on], null);
            }
            emit([doc.domain, leafLocation, 'all', sppId, doc.server_modified_on], null);
        }
    }
}
