function (doc) {
	if (doc.doc_type === 'CommCareCase') {
		if (doc.type) {
			emit(doc.domain, doc.actions);
		}
	}
}