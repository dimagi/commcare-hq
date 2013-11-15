function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'commtrack-requisition') {
        emit([doc.external_id, doc.product_id], null)
    }
}