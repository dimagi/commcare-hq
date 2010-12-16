function get_kind(obj) {
        var c = uneval(obj)[0];
        if (obj == null || obj == "") return 'null';
        else if (c == '(') return 'dict';
        else if (c == '[') return 'list';
        else return "string";
}

function get_export_tag_value(doc) {
    if (doc["#export_tag"]) {
        var pattern = doc["#export_tag"];
        var key;
        if (is_string(pattern)) {
            key = doc[pattern]
        }
        else {
            // assume it's a list
            key = [];
            for(var i in pattern) {
                key.push(doc[pattern[i]]);
            }
        }
        return key;
    }
    else if (doc["doc_type"]) {
        // This is the way other couchdbkit models are stored
        return doc["doc_type"];
    }
    return null;
}
    
function get_schema(doc) {
    var kind = get_kind(doc);
    var schema;
    if (kind == 'dict') {
        schema = {};
        for (var key in doc) {
            schema[key] = get_schema(doc[key]);
        }
    }
    else if (kind == 'list') {
        schema = [];
        for (var i in doc) {
            schema[i] = get_schema(doc[i]);
        }
    }
    else if (kind == 'string'){
        schema = "string";
    }
    else if (kind == 'null') {
        schema = null;
    }
    return reconcile(null, schema, 0);
}

function get_doc_schema(doc) {
    var export_tag_val = get_export_tag_value(doc);
    if (export_tag_val) {
        schema = get_schema(doc);
        schema["#export_tag_value"] = export_tag_val;
        return schema;
    }
}