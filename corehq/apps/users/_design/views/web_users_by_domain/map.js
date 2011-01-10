function(doc){ 
    if (doc.doc_type == "CouchUser" && doc.web_account.login_id != null) {
        var domain_memberships = doc.web_account.domain_memberships;
		for (var i in domain_memberships)
		{
	        emit(domain_memberships[i].domain,  null);
		}
    }
}
