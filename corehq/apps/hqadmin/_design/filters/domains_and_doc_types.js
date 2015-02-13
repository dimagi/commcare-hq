function (doc, req) {
    var domains_string = req.query.domains;
    var doc_types_string = req.query.doc_types;
    if (!(domains_string || doc_types_string)) {
        return false;
    }

    var domain_match = false,
        doc_type_match = false;
    if (domains_string) {
        var domains = domains_string.split(' ');
        if (domains.indexOf(doc.domain) >= 0) {
            domain_match = true;
        }
    } else {
        domain_match = true;
    }

    if (doc_types_string) {
        var doc_types = doc_types_string.split(' ');
        if (doc_types.indexOf(doc.doc_type) >= 0) {
            doc_type_match = true;
        }
    } else {
        doc_type_match = true;
    }
    return domain_match && doc_type_match;
}
