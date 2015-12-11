function(doc) {
    if (doc.base_doc === "CouchUser") {

        if (doc.doc_type === "CommCareUser" && doc.location_id) {
            emit([doc.domain, doc.location_id, doc.doc_type, doc._id], null);

        } else if (doc.doc_type === "WebUser") {
            for (var i = 0; i < doc.domain_memberships.length; i += 1) {
                var domain_membership = doc.domain_memberships[i];
                if (domain_membership.location_id) {
                    emit([
                        domain_membership.domain,
                        domain_membership.location_id,
                        doc.doc_type,
                        doc._id
                    ], null);
                }
            }
        }
    }
}
