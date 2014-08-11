function(doc){
    if(doc.doc_type == "CommCareCase") {
        for (var i = 0; i < doc.xform_ids.length; i++) {
            emit(doc.xform_ids[i], null);
        }
    }
}