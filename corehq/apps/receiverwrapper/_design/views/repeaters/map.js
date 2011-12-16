function(doc){
    if(doc.base_doc == "Repeater") {
        emit([doc.domain, doc.doc_type], null);
    }
}