function (doc, req) {
    return doc.doc_type === "Group" || doc.doc_type === "Group-Deleted";
}