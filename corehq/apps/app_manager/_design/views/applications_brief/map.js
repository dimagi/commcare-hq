function(doc){
    if((doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp') && doc.copy_of == null) {
        emit([doc.domain, doc.name], {
            doc_type: doc.doc_type,
            application_version: doc.doc_type === 'Application' ? doc.application_version || '1.0' : undefined,
            version: doc.version,
            _id: doc._id,
            name: doc.name,
            build_spec: doc.build_spec,
            domain: doc.domain,
            langs: doc.langs,
            case_sharing: doc.case_sharing
        });
    }
}