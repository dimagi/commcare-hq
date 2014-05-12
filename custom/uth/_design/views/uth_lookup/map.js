function(doc) {
    if (doc.type === "child" && doc.domain == "uth-rhd" && doc.scan_uploaded === "False") {
        emit([doc.domain, doc.vscan_serial, doc.scan_id, doc.scan_time], doc._id);
    }
}
