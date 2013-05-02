function(doc){
    if (doc.doc_type === 'Team'){
        for (i=0; i<doc.domains.length; i++){
            emit(doc.domains[i],null);
        }
    }
}