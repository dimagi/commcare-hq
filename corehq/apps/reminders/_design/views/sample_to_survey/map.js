function (doc) {
    if (doc.doc_type === "Survey") {
        if (doc.samples) {
            for (var i = 0; i < doc.samples.length; i++) {
                emit([doc.domain, doc.samples[i]["sample_id"], doc.samples[i]["method"]], null);
            }
        }
    }
}
