function(doc) {
    if (doc.type === "SonositeUpload") {
        emit([doc.domain, doc.case_id], doc._id);
    }
}
