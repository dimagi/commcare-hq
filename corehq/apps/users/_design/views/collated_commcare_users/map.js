function(doc) {
    if(doc.doc_type == "CouchUser") {
        var ids_by_domain = {};
        for(var i in doc.commcare_accounts) {
            var domain = doc.commcare_accounts[i].domain;
            if(!(domain in ids_by_domain)) {
                ids_by_domain[domain] = [];
            }
            ids_by_domain[domain].push(doc.commcare_accounts[i].login_id);
        }
        for(var domain in ids_by_domain) {
            emit([domain, doc._id], ids_by_domain[domain]);
        }
    }
}