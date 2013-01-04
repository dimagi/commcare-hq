function typeOf(value) {
    var s = typeof value;
    if (s === 'object') {
        if (value) {
            if (Object.prototype.toString.call(value) === '[object Array]') {
                s = 'array';
            }
        } else {
            s = 'null';
        }
    }
    return s;
}

function isArray(obj) {
    return typeOf(obj) === "array";
}

function isString(obj) {
    return typeOf(obj) === "string";
}

function getExportTagValue(doc) {
    if (doc["#export_tag"]) {
        var pattern = doc["#export_tag"];
        var key;
        if (isString(pattern)) {
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

function getExportDateValue(doc) {
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
