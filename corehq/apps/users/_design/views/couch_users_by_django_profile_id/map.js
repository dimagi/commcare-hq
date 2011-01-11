function(doc){
    if (doc.doc_type == "CouchUser") {
        if (doc.web_account.login_id) {
            emit(doc.web_account.login_id, null);
        }
        for (var i=0;i<doc.commcare_accounts.length;i++)
    	{
    		emit(doc.commcare_accounts[i].login_id, null);
    	}
    }
}