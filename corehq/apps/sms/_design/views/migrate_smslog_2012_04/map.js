function(doc) {
    if (doc.doc_type == "MessageLog") {
    	emit([doc._id], null);
    }
}
