function(doc){
    if(doc.doc_type == 'Application-Deleted' || doc.doc_type == 'RemoteApp-Deleted' || doc.doc_type == 'LinkedApplication-Deleted') {
        emit([doc.domain, doc.copy_of, doc.version], null);
        if (doc.is_released && doc.copy_of) {
            emit(['^ReleasedApplications', doc.domain,  doc.copy_of, doc.version], null);
        }
    }
}