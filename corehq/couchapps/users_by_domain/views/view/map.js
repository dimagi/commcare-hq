function (doc) {
    if (doc.base_doc === "CouchUser") {
        if (doc.doc_type === "WebUser") {
            for (var i = 0; i < doc.domain_memberships.length; i += 1) {
                var domainMembershipActive = doc.domain_memberships[i].is_active !== false;
                var active = (doc.is_active && domainMembershipActive) ? "active" : "inactive";
                emit([active, doc.domain_memberships[i].domain, doc.doc_type, doc.username],  null);
            }
        } else if (doc.doc_type === "CommCareUser") {
            var active = doc.is_active ? "active" : "inactive";
            emit([active, doc.domain, doc.doc_type, doc.username], null);
        }
    }
}
