function(doc){
    if(doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp' || doc.doc_type == 'LinkedApplication') {
        var origin_id = doc.copy_of || doc._id;
        var value = {
            doc_type: doc.doc_type,
            domain: doc.domain,
            _id: doc._id,
            copy_of: doc.copy_of,
            origin_id: origin_id,
            version: doc.version,
            is_released: doc.is_released,
            cloudcare_enabled: doc.cloudcare_enabled,
        };

        if (doc.copy_of) {
            emit(['BUILD', doc.domain, origin_id, doc.version], value);
            if (doc.is_released) {
                emit(['RELEASE', doc.domain, origin_id, doc.version], value);
            }
        } else {
            emit(['SAVE', doc.domain, origin_id, doc.version], value);
        }
    }
}
