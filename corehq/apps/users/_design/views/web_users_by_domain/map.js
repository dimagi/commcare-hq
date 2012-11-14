function (doc) {
    if (doc.doc_type == "WebUser" && doc.is_active) {
        var domain_memberships = doc.domain_memberships;
		for (var i = 0; i < domain_memberships.length; i++) {
            emit(domain_memberships[i].domain,  null);
		}
    }
}
