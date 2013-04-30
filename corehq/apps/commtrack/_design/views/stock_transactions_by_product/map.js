function(doc) {
    // !code util.js
    
    if (isCommTrackSubmission(doc)) {
        var transactions = normalizeRepeats(doc.form.transaction);

        for (var i = 0; i < transactions.length; i++) {
            var tx = eval(uneval(transactions[i]));
            tx.received_on = doc.received_on;

            emit([tx.product_entry, tx.received_on], tx);
        }
    }
}
