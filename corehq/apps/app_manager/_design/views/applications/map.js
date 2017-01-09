function(doc){
    if(doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp' || doc.doc_type == 'LinkedApplication') {
        emit([doc.domain, doc.copy_of, doc.version], null);
        // to search accross all domains
        emit([null, doc.copy_of, doc.version], null);

        if (doc.is_released && doc.copy_of) {
            emit(['^ReleasedApplications', doc.domain,  doc.copy_of, doc.version], null);
        }
    }
}