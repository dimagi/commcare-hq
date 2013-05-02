function (doc) {
    if (doc.base_doc === "CouchUser" && (!doc.hasOwnProperty("eula") || !doc.eula.signed)) {
        emit([doc.doc_type, doc.last_login], null);
    }
}
