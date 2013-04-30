function (doc, req) {
    var i,
        domains = req.query.domains.split(' '),
        domain_match = false;
    for (i = 0; i < domains.length; i++) {
        if (domains[i] === doc.domain) {
            domain_match = true;
            break;
        }
    }
    return (domain_match && doc.doc_type === req.query.doc_type);
}