function (doc) {
    // use "domains" as a hashset:
    // `domains[domain] = null` means `domains.add(domain)`
    var domains = {},
        domain,
        i;
    if (doc.base_doc === "CouchUser" && doc.is_active &&
            doc.phone_numbers !== null && doc.phone_numbers.length > 0) {
        if (doc.doc_type === "WebUser") {
            for (i = 0; i < doc.domain_memberships.length; i += 1) {
                domain = doc.domain_memberships[i].domain;
                domains[domain] = null;
            }
        } else if (doc.doc_type === "CommCareUser") {
            domains[doc.domain] = null;
        }


        for (domain in domains) {
            emit([domain, doc._id], null);
        }
    }
}