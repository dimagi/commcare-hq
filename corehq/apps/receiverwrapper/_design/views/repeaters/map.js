function(doc){
    if(doc.doc_type == "FormRepeater") {
        emit(doc.domain, null);
    }
}