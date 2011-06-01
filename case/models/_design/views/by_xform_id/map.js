function(doc){
    if(doc.doc_type == "CommCareCase") {
        emit(doc.xform_ids[0], null);
    }
}