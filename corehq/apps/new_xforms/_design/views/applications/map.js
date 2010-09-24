function(doc){
    if(doc.doc_type == 'Application') {
        emit([doc.domain, doc.trans.en], doc);
    }
}