function(doc){ 
    if (doc.doc_type == "CouchUser" && doc.phone_numbers != null && doc.phone_numbers.length > 0)
        var name = '';
        var phone_number = '';
        // get default phone number, if set
        phone_number = doc.phone_numbers[0];
        // get username from web user account
        if (doc.web_account != null)
        {
            django_id = doc.web_account.login_id
        	for (var i=0;i<doc.web_account.domain_memberships.length;i++)
        	{
                emit(doc.web_account.domain_memberships[i].domain,  {
                    django_id: django_id,
                    phone_number: phone_number,
                    id: doc['_id']
                });
        	}
        }
        else 
        {
        	// if no web user, use the latest commcare account
        	if (doc.commcare_accounts != null && doc.commcare_accounts.length > 0){
        		django_id = doc.commcare_accounts[0].django_user_id
            	for (var i=0;i<doc.commcare_accounts[0].domain_memberships.length;i++)
            	{
                    emit(doc.commcare_accounts[0].domain_memberships[i].domain,  {
                        django_id: django_id,
                        phone_number: phone_number,
                        id: doc['_id']
                    });
            	}
        	}
        }
}
