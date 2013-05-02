function typeOf(value) {
    // from Crockford himself: http://javascript.crockford.com/remedial.html
    var s = typeof value;
    if (s === 'object') {
        if (value) {
            if (Object.prototype.toString.call(value) == '[object Array]') {
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

function normalizeRepeats(prop) {
    if (prop) {
        return isArray(prop) ? prop : [prop];
    }
    else {
        return [];
    }
}

function isCommTrackSubmission (doc) {
    return ((doc.doc_type == "HQSubmission" || doc.doc_type == "XFormInstance") 
        && doc.xmlns == 'http://openrosa.org/commtrack/stock_report')  
}
