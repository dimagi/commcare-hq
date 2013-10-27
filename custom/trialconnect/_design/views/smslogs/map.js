function(doc) {
  if (["trialconnect", "tc-test", "gc"].indexOf(doc.domain) > -1 && doc.doc_type === "SMSLog") {
    	emit([doc.date], null);
    }
}
