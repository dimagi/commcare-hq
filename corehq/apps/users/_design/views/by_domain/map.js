function (doc) {
    var i;
    if (doc.base_doc === "CouchUser") {
        if (doc.doc_type === "WebUser") {
            for (i = 0; i < doc.domain_memberships.length; i += 1) {
                emit([doc.domain_memberships[i].domain, doc.doc_type],  null);
            }
        } else if (doc.doc_type === "CommCareUser") {
            emit([doc.domain, doc.doc_type], null);
        }
    }
}