function(doc) {
    if (doc.type === "magic_vscan_type" && doc.scan_uploaded === "False") {
        emit([doc.domain, doc.vscan_serial, doc.scan_id, doc.scan_time], doc._id);
    }
}
