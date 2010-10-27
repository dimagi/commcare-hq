function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/schema.js
    
    // You have to put however you want to access/group your schema here.
    if (doc["#export_tag"]) {
        var pattern = doc["#export_tag"];
        var key;
        if (uneval(pattern)[0] == '"') {
            key = doc[pattern]
        }
        else {
            key = [];
            for(var i in pattern) {
                key.push(doc[pattern[i]]);
            }
        }
        emit(key, get_schema(doc));
    }
    else if (doc["doc_type"]) {
        // This is the way other couchdbkit models are stored
        emit(doc["doc_type"], get_schema(doc));
    }
}