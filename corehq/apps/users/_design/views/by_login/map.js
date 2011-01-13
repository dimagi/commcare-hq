function(doc){
    if (doc.doc_type == "CouchUser") {
            emit(doc.web_account.login_id, null);
        for (var i in doc.commcare_accounts) {
            var account = doc.commcare_accounts[i];
            emit(account.login_id, null);
        }
    }
}