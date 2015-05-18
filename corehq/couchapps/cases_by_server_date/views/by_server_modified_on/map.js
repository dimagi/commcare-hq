function (doc) {
    if (doc.doc_type === "CommCareCase") {
        emit([doc.domain, doc._id], doc.server_modified_on);
    }
}
