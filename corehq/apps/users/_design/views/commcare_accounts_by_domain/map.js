function(doc) {
    if(doc.doc_type == "CouchUser") {
        for(var i in doc.commcare_accounts) {
            // make sure to group by doc
            emit([doc.commcare_accounts[i].domain, doc._id], doc.commcare_accounts[i]);
        }
    }
}