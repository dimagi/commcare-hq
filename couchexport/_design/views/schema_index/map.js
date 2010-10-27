function(doc) {
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
        emit(key, doc);
    }
    else if (doc["doc_type"]) {
        // This is the way other couchdbkit models are stored
        emit(doc["doc_type"], doc);
    }
}