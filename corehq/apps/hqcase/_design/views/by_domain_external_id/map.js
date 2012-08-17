function(doc){
	if(doc.doc_type == "CommCareCase") {
        emit([doc.domain, doc.external_id], null);
    }
}