function(doc){
    if(doc.doc_type == 'Application') {
        emit([doc.domain, doc.name.en], doc);
    }
}