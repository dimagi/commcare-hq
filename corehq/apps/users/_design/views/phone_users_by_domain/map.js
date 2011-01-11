function(doc){ 
    if (doc.django_type == "users.hquserprofile" && doc.phone_numbers != null && doc.phone_numbers.length > 0)
        var name = '';
        var phone_number = '';
        // get default phone number, if set
        for (var i=0;i<doc.phone_numbers.length;i++)
        {
            if (doc.phone_numbers[i].is_default == true){
                phone_number = doc.phone_numbers[i].number;
                break;
            }
        }
        if (phone_number==''){
            // if default not set, use last number added;
            phone_number = doc.phone_numbers[doc.phone_numbers.length-1].number;
        }
        // get username from web user account
        if (doc.django_user_id != null)
        {
            name = doc.django_user_id
        }
        else 
        {
        	// if no web user, use the latest commcare account username
           for (var i=doc.commcare_accounts.length-1;i>=0;i--)
            {
                if (doc.commcare_accounts[i].django_user_id != null){
                    name = doc.commcare_accounts[i].django_user_id
                    break
                }
            } 
        }
        // if no usernames found, return name as '' 
    	for (var i=0;i<doc.domain_memberships.length;i++)
    	{
            emit(doc.domain_memberships[i].domain,  {
                name: name,
                phone_number: phone_number,
                id: doc['_id']
            });
    	}
}
