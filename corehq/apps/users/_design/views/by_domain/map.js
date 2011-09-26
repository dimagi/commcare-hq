function (doc) {
    var i, active;
    if (doc.base_doc === "CouchUser") {
        active = doc.is_active ? "active" : "inactive";
        if (doc.doc_type === "WebUser") {
            for (i = 0; i < doc.domain_memberships.length; i += 1) {
                emit([active, doc.domain_memberships[i].domain, doc.doc_type, doc.username],  null);
            }
        } else if (doc.doc_type === "CommCareUser") {
            emit([active, doc.domain, doc.doc_type, doc.username], null);
        }
    }
}