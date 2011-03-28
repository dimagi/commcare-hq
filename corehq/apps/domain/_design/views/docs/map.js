function(doc){
    if(doc.doc_type && doc.domain) {
        emit([doc.doc_type, doc.domain, doc._id], null);
    }
}