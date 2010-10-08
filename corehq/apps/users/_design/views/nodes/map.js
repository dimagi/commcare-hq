function(doc){
    if(doc.doc_type == "DagNode") {
        emit(doc._id, doc);
    }
}