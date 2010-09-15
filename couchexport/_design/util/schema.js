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

    return schema;
}
    
    