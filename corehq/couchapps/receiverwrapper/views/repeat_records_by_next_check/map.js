function (doc) {
    if (doc.doc_type === 'RepeatRecord') {
        if (!doc.succeeded && !doc.cancelled) {
            emit([doc.domain, doc.next_check], null);
            emit([null, doc.next_check], null);
        }
    }
}
