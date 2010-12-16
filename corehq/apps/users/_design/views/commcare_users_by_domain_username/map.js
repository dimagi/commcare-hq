function(doc){ 
    if (doc.django_type == "users.hquserprofile")
    	for (var i=0;i<doc.commcare_accounts.length;i++)
    	{
    		emit([doc.commcare_accounts[i].domain, doc.commcare_accounts[i].django_user.username], 
    			  doc.commcare_accounts[i]);
    	}
}

