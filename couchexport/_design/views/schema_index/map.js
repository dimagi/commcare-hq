function(doc) {
    // !code util/types.js
    // !code util/schema.js
    tag = get_export_tag_value(doc); 
    if (tag) {
        var key = [];
        if (get_kind(tag) == 'list') {
            for (var i = 0; i < tag.length; i++) {
                key.push(tag[i]);
            }
        } else {
            key.push(tag);
        }
        key.push(get_export_date_value(doc));
        emit(key, null);
    }
    
}