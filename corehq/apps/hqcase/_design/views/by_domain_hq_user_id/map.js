function(doc){
    if(doc.doc_type == "CommCareCase") {
        emit([doc.domain, doc.hq_user_id], null);
    }
}
