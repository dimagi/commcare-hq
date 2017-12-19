function (doc) {
    var state = 'PENDING';
    if (doc.doc_type === 'RepeatRecord' || doc.doc_type === 'RepeatRecord-Failed') {
        if (doc.archived) {
            state = 'ARCHIVED';
        } else if (doc.cancelled) {
            state = 'SUCCESS';
        } else if (doc.cancelled) {
            state = 'CANCELLED';
        } else if (doc.failure_reason) {
            state = 'FAIL';
        }
        emit([doc.domain, doc.repeater_id, state, doc.last_checked], null);
        emit([doc.domain, null, state, doc.last_checked], null);
    }
}
