function(doc){
    if(doc.doc_type == "CommCareCase" && doc.hq_user_id) {
        emit([doc.domain, doc.hq_user_id, doc.type], null);
    }
}
