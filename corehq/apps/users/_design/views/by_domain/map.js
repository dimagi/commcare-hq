function(doc){ 
    if (doc.doc_type == "CouchUser") {
    	for (var i in doc.web_account.domain_memberships) {
            emit(doc.web_account.domain_memberships[i].domain,  null);
    	}
        for (var i in doc.commcare_accounts) {
            emit(doc.commcare_accounts[i].domain, null);
        }
    }
}

