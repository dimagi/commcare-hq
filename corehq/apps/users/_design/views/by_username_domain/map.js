function(doc){ 
    if (doc.django_type == "users.hquserprofile")
    	for (var i=0;i<doc.domain_accounts.length;i++)
    	{
            emit([doc.django_user.username, 
                  doc.domain_accounts[i].domain], 
                  doc);
    	}
}

