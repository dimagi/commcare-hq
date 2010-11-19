function(doc){
    if((doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp') && doc.copy_of == null) {
        emit([doc.domain, doc.name], {
            "doc_type": doc.doc_type,
            "version": doc.version,
            "id": doc._id,
            "name": doc.name
        });
    }
}