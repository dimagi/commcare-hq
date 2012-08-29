function(doc){
    if (doc.doc_type === 'Organization'){
        emit(doc.name,null);
    }
}