function(doc) {
    if (doc.doc_type == "Location") {
        emit([doc.domain, null, doc.name.toLowerCase()], null);
        emit([doc.domain, doc.location_type, doc.name.toLowerCase()], null);
    }
}
