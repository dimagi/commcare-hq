function(doc) {
    // !code util.js
    
    if (isCommTrackSubmission(doc)) {
        var leaf_location = doc.location_[doc.location_.length - 1];
        var transactions = normalizeRepeats(doc.form.transaction);
        var txn;
        for (var i = 0; i < transactions.length; i++) {
            txn = eval(uneval(transactions[i])); // the inbound doc is immutable
            txn['location_id'] = leaf_location;
            txn['received_on'] = doc.received_on;
            emit([doc.domain, leaf_location, doc.received_on], txn);
        }
    }
}
