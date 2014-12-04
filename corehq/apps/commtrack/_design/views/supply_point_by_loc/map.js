function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point') {
        emit([doc.domain, doc.location_id], null);
    }
}
