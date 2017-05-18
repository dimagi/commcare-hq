function(doc){
    if (doc.doc_type == "Group") {
        emit(doc.last_modified, null);
    } else if (doc.doc_type == "Domain") {
        emit(doc.last_modified, null);
    }
}
