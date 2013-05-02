function(doc) {
    if (doc.doc_type == "ForwardingRule") {
    	emit([doc.domain], null);
    }
}
