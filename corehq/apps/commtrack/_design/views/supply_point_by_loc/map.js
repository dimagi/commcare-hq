function(doc) {
    if (doc.doc_type == "CommCareCase" && doc.type == 'supply-point') {
        emit([doc.domain, doc.location_.slice(-1)[0]], null);
    }
}