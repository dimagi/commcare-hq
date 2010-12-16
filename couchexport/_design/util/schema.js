function get_kind(obj) {
        var c = uneval(obj)[0];
        if (obj == null || obj == "") return 'null';
        else if (c == '(') return 'dict';
        else if (c == '[') return 'list';
        else return "string";
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
    var export_tag_val = null;
    // we hard-codedly group either xforms by xmlns, or couchdbkit docs by model type 
    if (doc["#doc_type"] == "XForm") {
        export_tag_val = doc["@xmlns"];
    } else if (doc["doc_type"]) {
        export_tag_val = doc["doc_type"];
    }
    if (export_tag_val) {
        schema = get_schema(doc);
        schema["#export_tag_value"] = export_tag_val;
    return schema;
}
}