function(doc){
    if (doc.doc_type === "Group" || doc.doc_type === "Group-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    } else if (doc.doc_type === "Domain" || doc.doc_type === "Domain-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    } else if (doc.base_doc && (doc.base_doc === "CouchUser" || doc.base_doc === "CouchUser-Deleted")) {
        emit([doc.base_doc, doc.last_modified], null);
    } else if (doc.doc_type === "Application" || doc.doc_type === "Application-Deleted" ||
               doc.base_doc === "LinkedApplication" || doc.base_doc === "LinkedApplication-Deleted" ||
               doc.base_doc === "RemoteApp" || doc.base_doc === "RemoteApp-Deleted") {
        emit([doc.base_doc, doc.last_modified], null);
    }
}
