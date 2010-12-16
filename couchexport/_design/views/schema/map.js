function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/reconcile.js
    // !code util/schema.js
    
    schema = get_doc_schema(doc);
    if (schema) {
        emit(schema["#export_tag_value"], schema);
    }
}