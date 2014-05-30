function(doc) {
    if (doc.doc_type === "SonositeUpload") {
        emit([doc.doc_type, doc.study_id, doc.related_case_id], doc._id);
    }
    if (doc.doc_type === "VscanUpload") {
        emit([doc.doc_type, doc.scanner_serial, doc.scan_id], doc._id);
    }
}
