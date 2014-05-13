function(doc) {
    if (doc.type === "child" && doc.scan_status !== 'scan_complete' && doc.domain === "uth-rhd") {
        emit([doc.domain, 'VH014466XK', doc.exam_number, doc.scan_time], doc._id);
    }
}
