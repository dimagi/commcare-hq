function(doc){
    if (doc.doc_type === "Group" || doc.doc_type === "Group-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    } else if (doc.doc_type === "Domain" || doc.doc_type === "Domain-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    } else if (doc.base_doc && (doc.base_doc === "CouchUser" || doc.doc_type === "CouchUser-Deleted")) {
        emit([doc.base_doc, doc.last_modified], null);
    }
}
