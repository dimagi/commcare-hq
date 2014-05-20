function(doc) {
    if (doc.type === "child" && doc.scan_status !== 'scan_complete' && doc.domain === "uth-rhd") {
        emit([doc.domain, doc.scanner_serial, doc.exam_number], doc._id);
    }
}
