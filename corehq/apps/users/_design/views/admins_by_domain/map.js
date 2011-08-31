function (doc) {
    if (doc.doc_type == "WebUser") {
        var domain_memberships = doc.domain_memberships, i;
		for (i = 0; i < domain_memberships.length; i += 1) {
		    if (domain_memberships[i].is_admin) {
	           emit(domain_memberships[i].domain,  null);
	        }
		}
    }
}
