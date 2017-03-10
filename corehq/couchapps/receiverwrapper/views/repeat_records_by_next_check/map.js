function (doc) {
    if (doc.doc_type === 'RepeatRecord') {
        if (!doc.succeeded && doc.next_check && !doc.cancelled) {
            emit([doc.domain, doc.next_check], null);
            emit([null, doc.next_check], null);
        }
    }
}
