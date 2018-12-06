function(doc){
    if((doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp' || doc.doc_type == 'LinkedApplication' || doc.doc_type == 'Application-Deleted') &&
            doc.copy_of != null &&
            doc.has_submissions) {
        emit([doc.domain, doc.copy_of, doc.version], null);
    }
}
