function(doc){
    if(doc.doc_type == "CommCareCase") {
        emit([doc.domain, doc._id], null);
    }
}