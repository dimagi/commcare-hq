function(doc) { 
    if (doc["#doc_type"] == "XForm") 
        emit(doc._id, doc); 
}