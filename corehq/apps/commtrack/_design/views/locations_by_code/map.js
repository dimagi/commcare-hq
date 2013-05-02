function(doc) {
    if (doc.doc_type == "Location" && doc.site_code) {
        emit([doc.domain, doc.site_code.toLowerCase()], null);
    }
}
