function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'commtrack-requisition') {
        emit([doc.domain, doc.external_id], null)
    }
}