function (doc) {
    if (doc.doc_type === "SurveySample") {
        emit([doc.domain, doc.name], null);
    }
}
