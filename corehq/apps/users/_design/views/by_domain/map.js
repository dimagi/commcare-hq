function(doc){ 
    if (doc.doc_type == "CouchUser") {
    	for (var i in doc.web_account.domain_memberships) {
            emit(doc.web_account.domain_memberships[i].domain,  null);
    	}
    }
}

