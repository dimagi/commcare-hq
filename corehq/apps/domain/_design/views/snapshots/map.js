function (doc) {
    if (doc.doc_type == 'Domain' && doc.is_snapshot) {
        emit([doc.original_doc, doc.snapshot_time], null);
    }
}