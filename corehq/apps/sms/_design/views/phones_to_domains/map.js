function (doc) {
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
            for (i = 0; i < doc.phone_numbers.length; i += 1) {
                emit(doc.phone_numbers[i], domain);
            }
        }
    }
}