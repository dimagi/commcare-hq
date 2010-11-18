function(doc){
    if((doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp') && doc.copy_of != null) {
        emit([doc.domain, doc.copy_of, doc.version], {
            "copy_of": doc.copy_of,
            "short_url": doc.short_url,
            "version": doc.version,
            "id": doc._id
        });
    }
}