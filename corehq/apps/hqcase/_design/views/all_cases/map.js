function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id ) {
        emit([doc.domain, doc.type, doc.user_id, doc.modified_on], 1);
        emit([doc.domain, {}, doc.user_id, doc.modified_on], 1);
        emit([doc.domain, doc.type, {}, doc.modified_on], 1);
        emit([doc.domain, {}, {}, doc.modified_on], 1);
    }
}