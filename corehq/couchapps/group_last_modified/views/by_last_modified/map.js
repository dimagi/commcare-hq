function(doc){
    if (doc.doc_type == "Group") {
        emit(doc.last_modified, null);
    }
}
