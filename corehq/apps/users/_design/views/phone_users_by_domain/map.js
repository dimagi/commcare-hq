function(doc){
    if (doc.doc_type == "CouchUser" && doc.phone_numbers != null && doc.phone_numbers.length > 0) {
        for(var dm in doc.web_account.domain_memberships) {
            var domain = doc.web_account.domain_memberships[dm].domain;
            emit([domain, doc._id], null);
        }
        for(var ca in doc.commcare_accounts) {
            var domain = doc.commcare_accounts[ca].domain;
            emit([domain, doc._id], null);
        }
    }
}