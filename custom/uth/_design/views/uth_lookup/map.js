function(doc) {
    if (doc.type === 'magic_vscan_type') {
        // emit([doc.domain, doc.scan_id], null);
        // emit([doc.domain, doc.vscan_serial], null);
        emit([doc.domain, doc.vscan_serial, doc.scan_id], doc._id);
    }
}
