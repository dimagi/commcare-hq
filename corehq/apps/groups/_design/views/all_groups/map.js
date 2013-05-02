function(doc){ 
    if (doc.doc_type == "Group")
        emit(doc._id, null);
}