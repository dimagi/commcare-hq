function(doc){ 
    if (doc.django_type == "users.hquserprofile" && doc.django_user.username != null)
		for (var i=0;i<doc.domain_memberships.length;i++)
		{
	        emit(doc.domain_memberships[i].domain,  doc);
		}
}
