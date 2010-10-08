function(doc){
    if(doc.doc_type == "DagNode") {
        for(var i in doc.child_ids) {
            emit(doc.child_ids[i], doc);
        }
    }
}