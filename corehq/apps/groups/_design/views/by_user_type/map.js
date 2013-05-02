function (doc) {
    if (doc.doc_type === "Group" && doc.metadata && doc.metadata.user_type) {
        emit([doc.domain, doc.metadata.user_type], null);
    }
}
