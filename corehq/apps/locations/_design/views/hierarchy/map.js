function(doc) {
    if (doc.doc_type == "Location") {
	var path = [doc.domain];
	for (var i = doc.lineage.length - 1; i >= 0; i--) {
	    path.push(doc.lineage[i]);
	}
	path.push(doc._id);

	emit(path, null);
    }
}
