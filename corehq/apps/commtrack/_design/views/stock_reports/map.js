function(doc) {
    if (doc.doc_type == "HQSubmission" && doc.xmlns == 'http://openrosa.org/commtrack/stock_report') {
	emit([doc.domain, doc.received_on], null);
    }
}
