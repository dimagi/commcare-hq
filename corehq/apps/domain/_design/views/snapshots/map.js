function (doc) {
    if (doc.doc_type == 'Domain' && doc.is_snapshot) {
        emit([doc.copy_history[doc.copy_history.length - 1], doc.snapshot_time], null);
    }
}