function(doc){ 
    if (doc.django_type == "users.hquserprofile")
    	for (var i=0;i<doc.commcare_accounts.length;i++)
    	{
    		emit(doc._id, doc.commcare_accounts[i]);
    	}
}

