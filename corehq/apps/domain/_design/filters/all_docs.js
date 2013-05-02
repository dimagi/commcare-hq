function (doc, req) {
    var i, domain = req.query.domain;
    if (doc.domain === undefined && doc.domains === undefined) {
        return false;
    } else if (doc.domain === domain) {
        return true;
    } else if (doc.domains && doc.domains.length) {
        for (i = 0; i < doc.domains.length; i += 1) {
            if (doc.domains[i] === domain) {
                return true;
            }
        }
    } else {
        return false;
    }
}