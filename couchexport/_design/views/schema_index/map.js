function(doc) {
    // !code util/types.js
    // !code util/schema.js
    tag = get_export_tag_value(doc); 
    if (tag) {
        emit(tag, doc);
    }
    
}