function (doc, req) {
    var domain_match = false;
    if (req.query.domains){
        var i,
        domains = req.query.domains.split(' ');
        for (i = 0; i < domains.length; i++) {
            if (domains[i] === doc.domain) {
                domain_match = true;
                break;
            }
        }
    } else {
        domain_match = true;
    }

    var doc_type_match = true;
    if (req.query.doc_type) {
        doc_type_match = doc.doc_type === req.query.doc_type;
    }

    return (domain_match && doc_type_match);
}