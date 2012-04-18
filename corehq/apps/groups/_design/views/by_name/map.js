function(doc){ 
    if (doc.doc_type == "Group") {
        emit([doc.domain, doc.name],  null);
        if (doc.reporting || doc.reporting === undefined) {
            emit(['^Reporting', doc.domain, doc.name],  null);
        }
    }
}