function(doc) {
    if (doc.type === "SonositeUpload" || doc.type === "VscanUpload") {
        emit([doc.domain, doc.type, doc.case_id], doc._id);
    }
}
