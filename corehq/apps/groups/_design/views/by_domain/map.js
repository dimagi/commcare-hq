function(doc){ 
    if (doc.doc_type == "Group") {
        emit(doc.domain,  null);
    }
}

