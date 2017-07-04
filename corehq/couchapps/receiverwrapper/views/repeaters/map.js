function(doc){
    // grandfather in old FormRepeater docs
    if(doc.base_doc === "Repeater" || doc.doc_type === "FormRepeater") {
        emit([doc.domain, doc.doc_type], null);
    }
}