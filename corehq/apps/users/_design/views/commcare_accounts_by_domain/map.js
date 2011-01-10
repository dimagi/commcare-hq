function(doc) {
    if(doc.doc_type == "CouchUser") {
        for(var i in doc.commcare_accounts) {
            emit(doc.commcare_accounts[i].domain, doc.commcare_accounts[i]);
        }
    }
}