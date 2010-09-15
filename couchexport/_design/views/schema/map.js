function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/schema.js
    
    // You have to put however you want to access/group your schema here.
    if (doc["#export_tag"]) {
        emit(doc[doc["#export_tag"]], get_schema(doc));
    }
    else if (doc["doc_type"]) {
        // This is the way other couchdbkit models are stored
        emit(doc["doc_type"], get_schema(doc));
    }
}