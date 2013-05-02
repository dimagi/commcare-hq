function(doc){
    if (doc.doc_type === 'Team'){
        emit([doc.organization, doc.name],null);
    }
}