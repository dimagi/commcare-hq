function (doc) {
    var state = 'PENDING';
    if (doc.doc_type === 'RepeatRecord' || doc.doc_type === 'RepeatRecord-Failed') {
        if (doc.succeeded) {
            state = 'SUCCESS';
        } else if (doc.cancelled) {
            state = 'CANCELLED';
        } else if (doc.failure_reason) {
            state = 'FAIL';
        }
        emit([doc.domain, doc.repeater_id, state], null);
        emit([doc.domain, null, state], null);
    }
}
