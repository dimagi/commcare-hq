function(doc) { 
    if (doc["doc_type"] == "XFormInstance")
        emit(doc._id, doc); 
}