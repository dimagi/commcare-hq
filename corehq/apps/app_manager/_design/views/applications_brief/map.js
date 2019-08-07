function(doc){
    if((doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp' || doc.doc_type == 'LinkedApplication') && doc.copy_of == null) {
        emit([doc.domain, doc._id], {
            doc_type: doc.doc_type,
            application_version: doc.doc_type === 'Application' ? doc.application_version : undefined,
            version: doc.version,
            _id: doc._id,
            name: doc.name,
            build_spec: doc.build_spec,
            domain: doc.domain,
            langs: doc.langs,
            cached_properties: doc.cached_properties,
            case_sharing: doc.case_sharing,
            cloudcare_enabled: doc.cloudcare_enabled,
            mobile_ucr_sync_interval: doc.mobile_ucr_sync_interval,
            created_from_template: doc.created_from_template,
            progenitor_app_id: doc.progenitor_app_id,
        });
    }
}
