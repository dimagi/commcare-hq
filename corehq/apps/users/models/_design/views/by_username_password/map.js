function(doc){ 
    if (doc.django_type == "users.hquserprofile")
    	for (var i=0;i<doc.domain_accounts.length;i++)
    	{
            emit([doc.domain_accounts[i].username, 
                  doc.django_user.password, 
                  doc.domain_accounts[i].domain], 
                  doc);
    	}
}

