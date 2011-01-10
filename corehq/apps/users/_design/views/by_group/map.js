function(doc){ 
    if (doc.doc_type == "Group") {
    	for (var i=0;i<doc.users.length;i++) {
            emit([doc.domain, doc.name],  {'_id': doc.users[i]});
    	}
    }
}
