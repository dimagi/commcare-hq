function(doc){ 
    if (doc.django_type == "users.hquserprofile") {
    	for (var i=0;i<doc.domain_memberships.length;i++)
    	{
            emit([doc.domain_memberships[i].domain, doc.django_user.username], null);
    	}
        for (var i in doc.commcare_accounts) {
            var account = doc.commcare_accounts[i];
            emit([account.domain, account.django_user.username], null);
        }
    }
}

