function (doc) {
    if (doc.doc_type == 'Domain' && doc.is_snapshot && doc.published) {
        emit([doc.is_approved, doc.snapshot_time], null);
    }
}