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
    return null;
}

function get_export_date_value(doc) {
    if (doc["#export_tag"]) {
        var property;
        // this is the "generic" way to do this
        if (doc["#export_date"]) {
            property = doc["#export_date"];
        } else {
            // these are hacks to make this easier to work with current known
            // supported projects, which are now grandfathered in.
            var taggedLikeForm = function (tag) {
                return tag === "xmlns";
            };
            var taggedLikeHQForm = function (tag) {
                return tag.length === 2 && tag[0] === "domain" && tag[1] === "xmlns";
            };
            var taggedLikeHQCase = function (tag) {
                return tag.length === 2 && tag[0] === "domain" && tag[1] === "type";
            };
            var tag = doc["#export_tag"];
            if (taggedLikeForm(tag) || taggedLikeHQForm(tag)) {
                property = "received_on";
            } else if (taggedLikeHQCase(tag)) {
                property = "server_modified_on";
            }
        }
        if (property) {
            return doc[property];
        }
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