function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'commtrack-requisition') {
        var getSupplyPointCaseId = function (doc) {
            for (var i = 0; i < doc.indices.length; i++) {
                if (doc.indices[i].identifier === 'parent_id') {
                    return doc.indices[i].referenced_id;
                }
            }
        }

        var spId = getSupplyPointCaseId(doc);

        if (spId) {
            if (!doc.closed) {
                emit([doc.domain, spId, 'open', doc.server_modified_on], null);
            }
            emit([doc.domain, spId, 'all', doc.server_modified_on], null);
        }
    }
}
