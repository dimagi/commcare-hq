function(doc){
    if(doc.doc_type == "CommCareCase") {
        emit(doc.xform_id, null);
    }
}