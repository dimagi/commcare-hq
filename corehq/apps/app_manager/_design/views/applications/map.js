function(doc){
    if(doc.doc_type == 'Application') {
        emit([doc.domain, doc.copy_of, doc.version], doc);
    }
}