function(doc){ 
    if (doc.doc_type == "Groupb")
        emit(doc.domain,  doc);
}

