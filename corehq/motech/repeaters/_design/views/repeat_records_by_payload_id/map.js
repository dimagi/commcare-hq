function (doc) {
    if (doc.doc_type === 'RepeatRecord' || doc.doc_type === 'RepeatRecord-Failed') {
        emit([doc.domain, doc.payload_id], null);
    }
}
