function(doc){ 
    if (doc.django_type == "users.hquserprofile" && doc.phone_numbers != null && doc.phone_numbers.length > 0)
        var name = '';
        var phone_number = '';
        for (var i=0;i<doc.phone_numbers.length;i++)
        {
            if (doc.phone_numbers[i].is_default == true){
                phone_number = doc.phone_numbers[i].number;
                break;
            }
        }
        if (phone_number==''){
            // default to the last number added;
            phone_number = doc.phone_numbers[doc.phone_numbers.length-1].number;
        }
        if (doc.django_user.username != null && doc.django_user.username.length > 0)
        {
            name = doc.django_user.username
        }
        else 
        {
            for (var i=0;i<doc.commcare_accounts.length;i++)
            {
                if (doc.commcare_accounts[i].django_user.username.length > 0){
                    name = doc.commcare_accounts[i].django_user.username
                    break
                }
            } 
        }
    	for (var i=0;i<doc.domain_memberships.length;i++)
    	{
            emit(doc.domain_memberships[i].domain,  [name, phone_number]);
    	}
}
