function(doc){
    if (doc.doc_type == "Group" || doc.doc_type == "Group-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    } else if (doc.doc_type == "Domain" || doc.doc_type == "Domain-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    } else if (doc.doc_type == "WebUser" ||
               doc.doc_type == "WebUser-Deleted" ||
               doc.doc_type == "CommCareUser" ||
               doc.doc_type == "CommCareUser-Deleted") {
        emit([doc.doc_type, doc.last_modified], null);
    }
}
