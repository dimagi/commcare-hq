function(doc){
    if((doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp' || doc.doc_type == 'LinkedApplication') && doc.copy_of != null) {
        emit([doc.domain, doc.copy_of, doc.version], {
            doc_type: doc.doc_type,
            short_url: doc.short_url,
            short_odk_url: doc.short_odk_url,
            short_odk_media_url: doc.short_odk_media_url,
            version: doc.version,
            _id: doc._id,
            name: doc.name,
            build_spec: doc.build_spec,
            text_input: doc.text_input,
            platform: doc.platform,
            copy_of: doc.copy_of,
            domain: doc.domain,
            built_on: doc.built_on,
            built_with: doc.built_with,
            build_comment: doc.build_comment,
            build_broken: doc.build_broken,
            comment_from: doc.comment_from,
            is_released: doc.is_released,
            case_sharing: doc.case_sharing,
            build_profiles: doc.build_profiles,
            vellum_case_management: !!doc.vellum_case_management
        });
    }
}
