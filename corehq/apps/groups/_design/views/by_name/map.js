function(doc){ 
    if (doc.doc_type == "Group")
        emit(doc.name,  doc);
}

