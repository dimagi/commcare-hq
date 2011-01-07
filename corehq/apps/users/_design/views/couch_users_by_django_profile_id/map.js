function(doc){ 
    if (doc.doc_type == "CouchUser") {
        if (doc.django_user_id) {
            emit(doc.django_user_id, null);
        }
        for (var i=0;i<doc.commcare_accounts.length;i++)
    	{
    		emit(doc.commcare_accounts[i].django_user_id, null);
    	}
    }
}