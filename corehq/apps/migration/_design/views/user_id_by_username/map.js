function(doc){
    if(doc.doc_type == "MigrationUser") {
        emit([doc.domain, doc.username], doc.user_id);
    }
}