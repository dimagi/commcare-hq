function(doc) {
    if (doc.doc_type === 'CommCareCase') {
        emit([doc.domain, doc.type, doc.block], 1);
    }
}