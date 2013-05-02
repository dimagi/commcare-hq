function (doc) {
    if (doc.doc_type === "Location" && doc.outlet_type) {
        emit([doc.domain, doc.outlet_type], null);
    }
}