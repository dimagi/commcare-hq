function(doc){ 
    if (doc.doc_type == "CouchUser")
    	for (var i=0;i<doc.commcare_accounts.length;i++)
    	{
    		emit([doc.commcare_accounts[i].domain, doc.commcare_accounts[i].login_id],
    			  doc.commcare_accounts[i]);
    	}
}

