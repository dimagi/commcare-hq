function(doc){ 
    if (doc.doc_type == "Group") {
        emit([doc.domain, doc.name],  null);
    }
}

