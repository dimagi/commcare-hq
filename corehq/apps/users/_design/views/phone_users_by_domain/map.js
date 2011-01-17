function(doc){
    // use "domains" as a hashset:
    // `domains[domain] = null` means `domains.add(domain)`
    var domains = {};
    if (doc.doc_type == "CouchUser" && doc.phone_numbers != null && doc.phone_numbers.length > 0) {
        for(var dm in doc.web_account.domain_memberships) {
            var domain = doc.web_account.domain_memberships[dm].domain;
            domains[domain] = null;
        }
        for(var ca in doc.commcare_accounts) {
            var domain = doc.commcare_accounts[ca].domain;
            domains[domain] = null;
        }

        for(var domain in domains) {
            emit([domain, doc._id], null);
        }
    }
}