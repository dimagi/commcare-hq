function (doc) {
    if (doc.doc_type == 'Domain' && doc.is_snapshot && doc.published) {
        emit([doc.original_doc, Date.parse(doc.snapshot_time).getTime()], null);
    }
}