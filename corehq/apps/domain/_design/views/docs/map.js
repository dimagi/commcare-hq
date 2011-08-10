function (doc) {
    var i;
    if (doc.doc_type) {
        if (doc.domain) {
            emit([doc.domain, doc.doc_type, doc._id], null);
        }
        if (doc.domains && doc.domains.length) {
            for (i = 0; i < doc.domains.length; i += 1) {
                emit([doc.domains[i], doc.doc_type, doc._id], null);
            }
        }
    }
}