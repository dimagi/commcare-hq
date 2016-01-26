function(doc){
    if((doc.doc_type === 'Application') && doc.copy_of === null && doc.cloudcare_enabled) {
        emit([doc.domain, doc.name], {
            doc_type: doc.doc_type,
            application_version: doc.doc_type === 'Application' ? doc.application_version || '1.0' : undefined,
            version: doc.version,
            _id: doc._id,
            name: doc.name,
            build_spec: doc.build_spec,
            domain: doc.domain,
            cloudcare_enabled: doc.cloudcare_enabled
        });
    }
}
