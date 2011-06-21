function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id ) {
        emit([doc.domain, doc.user_id, doc.modified_on], 1);
    }
}