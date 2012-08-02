function(doc){
    var i;
    if (doc.doc_type === "Group") {
    	for (i = 0; i < doc.users.length; i++) {
    		emit(doc.users[i], [doc.domain, doc.name]);
    	}
    }
}

