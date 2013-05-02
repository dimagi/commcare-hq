function (doc) {
    if (doc.doc_type === "Group" && doc.metadata && doc.metadata.child_type) {
        var m = doc.metadata;

        emit([doc.domain, m.owner_type, m.child_type, m.owner_name], null);
    }
}
